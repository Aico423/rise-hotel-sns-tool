# RISE HOTEL SNS自動投稿ツール

客室写真とキーワードから、毎日自動でSNS投稿画像を生成し、X（旧Twitter）へ投稿するツールです。
Instagram / Facebook / Google ビジネスプロフィールへの投稿はコードとして実装済みですが、
Meta App Review・Googleのアクセス審査が承認されるまでは無効化（dry-run）された状態で納品しています。

対象読者: このツールを保守する担当者（開発仕様書を書かれた方）向けです。
ホテルスタッフが日常的に使うのは「管理画面」（後述）だけで、このREADMEを読む必要はありません。

---

## 1. 全体構成

```
data/                 素材データ（客室写真・投稿文言・タグ設定・投稿履歴）
admin/rise_sns/          画像生成・キャプション合成・各SNS投稿のPythonパッケージ
scripts/run_daily_post.py  GitHub Actionsから毎日呼ばれる本体処理
.github/workflows/      GitHub Actionsのスケジュール設定
admin/                 スタッフ向け管理画面（Vercelにデプロイして使う）
tests/                 ユニットテスト（pytest）
```

- 素材（画像・文言）は **このリポジトリを公開（public）にする前提** で `data/` 配下に保存します。
  客室写真はいずれ公にSNS投稿する素材のため非公開にする必要が薄く、Instagram等が要求する
  「公開URL経由の画像参照」もそのまま使えるようにしています。認証情報（APIキー等）は
  リポジトリには一切含めません（GitHub Secrets / Vercelの環境変数のみで管理）。
- 管理画面（`admin/`）は Vercel にデプロイし、GitHub Contents API 経由でこのリポジトリの
  `data/` ファイルを直接読み書きします。

---

## 2. 動作の流れ

1. 毎日、GitHub Actions が起動（`.github/workflows/daily-post.yml`）
2. 登録済みの客室写真・投稿文言から、季節や直近の投稿履歴を考慮して1組選ぶ
3. Google Gemini API（画像編集モデル。通称「Nano Banana 2」）で客室写真に人物等を合成
4. Pillowでキーワードを含む文章を画像に焼き込み、SNSごとのサイズに変換
5. 登録済みのスタンプ・ハッシュタグ画像（`admin/rise_sns/decorations.py`）から、その日の写真・文言のタグと
   一致するものを自動選定し、四隅・上下中央のいずれかに合成する（一致するものが無ければ何も挿入しない）
6. X（有効）／Instagram・Facebook・Google Business（無効化中）へ投稿を試みる
7. 投稿履歴を記録し、失敗があればSlackへ通知（設定していれば）

**スタンプ・ハッシュタグ画像について**: 「BOOK NOW」のような予約訴求バッジや、地名・キャンペーンの
ハッシュタグ風グラフィックは、管理画面の「スタンプを登録する」から透過PNG等をアップロードし、
関連キーワード（タグ）を紐づけて登録する。投稿文言側にも「関連キーワード」を任意で登録でき、
両者のタグが1つでも一致すると自動的に画像へ合成される。なお、Instagram/FacebookのGraph APIは
ネイティブのインタラクティブスタンプ（タップ可能なリンク等）を追加できないため、これはあくまで
「投稿前の画像そのものに視覚的な装飾として焼き込む」方式である。

---

## 3. 環境変数一覧

`.env.example` をコピーして `.env` を作成し、値を入れてください（ローカル確認用。**絶対にコミットしないこと**）。
本番運用では GitHub Secrets / Variables と Vercelの環境変数に設定します（詳細は5・6章）。

| 変数名 | 用途 |
|---|---|
| `GITHUB_REPO` | `owner/repo` 形式。生成画像の公開URL組み立て、Actionsからのpush先 |
| `GITHUB_BRANCH` | 既定 `main` |
| `GEMINI_API_KEY` | Gemini API キー |
| `GEMINI_IMAGE_MODEL` | 画像編集モデルID（**要確認、下記「注意点」参照**） |
| `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | X投稿用（OAuth1.0a） |
| `X_BEARER_TOKEN` | 未使用（アプリ単体認証のため投稿には使えない。将来の読み取り用途に予約） |
| `META_ACCESS_TOKEN` / `IG_USER_ID` / `FACEBOOK_PAGE_ID` | Meta（Instagram/Facebook）用。承認後に使用 |
| `FACEBOOK_POST_MODE` | `feed`（既定）または `story`。**下記「注意点」参照** |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` / `GOOGLE_BUSINESS_ACCOUNT_ID` / `GOOGLE_BUSINESS_LOCATION_ID` | Google Business Profile用。承認後に使用 |
| `ENABLE_X` / `ENABLE_INSTAGRAM` / `ENABLE_FACEBOOK` / `ENABLE_GOOGLE_BUSINESS` | 本番投稿の有効/無効スイッチ |
| `SLACK_WEBHOOK_URL` | 失敗時の通知先（任意） |
| `GITHUB_PAT` | **管理画面（Vercel）側のみ**で使用。このリポジトリ限定・Contents読み書き権限のみのfine-grained PAT |
| `FLASK_SECRET_KEY` | **管理画面（Vercel）側のみ**。ログインセッションの署名鍵（ランダムな文字列） |
| `KV_REST_API_URL` / `KV_REST_API_TOKEN` | **管理画面（Vercel）側のみ**。ユーザーアカウント（メールアドレス・パスワードのハッシュ値）の保存先。VercelのStorageからUpstash(Redis)を接続すると自動注入される（`UPSTASH_REDIS_REST_URL`等が注入された場合も自動的に使われる） |

---

## 4. ローカルでの動作確認

このプロジェクトはPython 3.11以降を想定しています。ローカルにPythonが入っていない場合は
[python.org](https://www.python.org/downloads/) からインストールしてください。

```bash
pip install -r requirements.txt
cp .env.example .env
# .envを編集して値を入れる（本番キーが無くてもテストは通ります）
PYTHONPATH=admin pytest -q
```

日本語フォント（Noto Sans JP）は `assets/fonts/NotoSansJP-Bold.ttf` としてリポジトリに同梱済みです
（管理画面のプレビュー機能でも同じフォントを使うため、GitHub Actions実行時のみ取得する方式から、
リポジトリに同梱する方式に変更しています）。

バッチ処理本体を試す場合:

```bash
PYTHONPATH=admin python scripts/run_daily_post.py
```

（`ENABLE_X=false` 等にしておけば、実際には投稿されずログにのみ記録されます。）

Windowsのコマンドプロンプト/Git Bashでログの日本語が文字化けする場合は、`PYTHONIOENCODING=utf-8`
を付けて実行してください（表示だけの問題で、GitHub Actions上では発生しません）。

---

## 5. GitHubリポジトリの作成・公開

1. GitHub上で新しいリポジトリを作成する（**Public** を推奨。理由は1章参照）
2. このフォルダの内容をpushする：

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<your-account>/<repo-name>.git
git push -u origin main
```

3. リポジトリの Settings → Secrets and variables → Actions で、以下を登録する
   - **Secrets**（値を隠す必要があるもの）: `GEMINI_API_KEY`, `X_API_KEY`, `X_API_SECRET`,
     `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`, `META_ACCESS_TOKEN`, `GOOGLE_CLIENT_ID`,
     `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `SLACK_WEBHOOK_URL`
   - **Variables**（隠さなくてよい設定値）: `IG_USER_ID`, `FACEBOOK_PAGE_ID`, `FACEBOOK_POST_MODE`,
     `GOOGLE_BUSINESS_ACCOUNT_ID`, `GOOGLE_BUSINESS_LOCATION_ID`, `GEMINI_IMAGE_MODEL`,
     `ENABLE_X`, `ENABLE_INSTAGRAM`, `ENABLE_FACEBOOK`, `ENABLE_GOOGLE_BUSINESS`

Meta・Googleの審査が承認されるまでは `ENABLE_INSTAGRAM` / `ENABLE_FACEBOOK` / `ENABLE_GOOGLE_BUSINESS`
を設定しない（未設定＝無効）ままにしておいてください。

---

## 6. 管理画面（Vercel）のデプロイ手順

1. [Vercel](https://vercel.com/) にアカウント作成し、GitHubと連携する
2. 「New Project」から、このリポジトリをインポートする
3. **Root Directory** を `admin` に設定する
4. Environment Variables に以下を設定する
   - `GITHUB_PAT`: このリポジトリ限定・Contentsの読み書き権限のみを持つ fine-grained PAT
     （GitHubの Settings → Developer settings → Personal access tokens → Fine-grained tokens で発行）
   - `GITHUB_REPO`: `owner/repo` 形式
   - `GITHUB_BRANCH`: `main`
   - `FLASK_SECRET_KEY`: ランダムな文字列（ローカルで `python -c "import secrets; print(secrets.token_hex(32))"` を実行して生成したものを貼り付ける）
5. デプロイ完了後に発行されるURLをスタッフに共有する

管理画面はスタッフがブラウザで開くだけで使えます。API・JSON等の専門用語は画面上に一切表示されません。

### 6-1. ログイン機能とユーザーデータの保存先（Upstash Redis）

管理画面にはメールアドレス・パスワードによるログインが必要です。ユーザーアカウント情報は、
GitHubリポジトリ（Gitは履歴が残るため、パスワード変更・削除後も古いハッシュ値が残ってしまう）
ではなく、Upstash Redis（Vercel Marketplace経由）に保存する。

1. Vercelのプロジェクト画面で「**Storage**」タブを開く
2. 「**Marketplace Database Providers**」（または類似の名称）から「**Upstash**」を探して追加する
3. Redis形式のデータベースを新規作成し、このプロジェクトに接続（Connect）する
4. 接続すると `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` が自動的に環境変数として追加される（自分で入力する必要はない）
5. 再デプロイ後、管理画面のURLを開くと「初期設定：管理者アカウントを作成」画面が表示されるので、
   最初の管理者アカウント（メールアドレス・パスワード）をブラウザから直接作成する
   （このパスワードは開発者側では一切見えない・保存されない）
6. 以降、管理者アカウントでログインし「ユーザー管理」画面から他のスタッフのアカウントを追加できる

---

## 7. Meta / Google 承認後にやること

1. `META_ACCESS_TOKEN` 等の値をGitHub Secretsに設定する
2. `ENABLE_INSTAGRAM` / `ENABLE_FACEBOOK` / `ENABLE_GOOGLE_BUSINESS` を `true` に変更する
   （Settings → Secrets and variables → Actions → Variables タブ）
3. 次回のスケジュール実行、または「Actions」タブから `workflow_dispatch` で手動実行して動作確認する

コードの変更は一切不要です。

---

## 8. 実装時点での注意点・要検証事項

以下は、Meta/GoogleのAPI仕様が変わりやすい・不確実な部分です。**本番投稿を有効化する前に、
必ず各社の最新ドキュメントで確認してください。**

- **Gemini画像編集モデルID**（`GEMINI_IMAGE_MODEL`）: 「Nano Banana 2」はマーケティング上の
  通称でAPIのモデルIDではありません。既定値は暫定的なものです。Google AI Studio / Gemini API
  ドキュメントで現時点の正式なモデルIDを確認し、必要なら環境変数で上書きしてください。
- **Facebookページのストーリー投稿**（`FACEBOOK_POST_MODE=story`）: 本実装時点でPage写真の
  ストーリー公開APIの正式なエンドポイント名が確認できていません（`FACEBOOK_STORY_ENDPOINT`
  環境変数で上書き可能にしてあります）。確認が取れるまでは既定の `feed`（通常投稿）を
  使うことを推奨します。
- **Google Business Profile API**: 第三者アプリへの投稿権限付与自体が一般的にかなり制限されて
  おり、ホテル単体の申請では承認されない可能性があります。コードは完成させていますが、
  恒久的にスタッフによる手動投稿が必要になる可能性も想定しておいてください。
- **Instagram/Facebookの画像URL**: Graph APIの `media_type=STORIES` は公開URLを要求するため、
  本番投稿を有効化すると、生成画像を自動でこのリポジトリにコミット・pushします
  （`raw.githubusercontent.com` 経由で参照するため）。
- **管理画面のCSRF対策**: セッションCookieは `HttpOnly`・`Secure`・`SameSite=Lax` を設定しているが、
  専用のCSRFトークンまでは実装していない。小規模な社内ツール向けの現実的な落とし所としての判断。
  より厳密な対策が必要な場合は追加実装を検討すること。

---

## 9. テスト

```bash
PYTHONPATH=admin pytest -q
```

GitHub Actionsのワークフロー内でも、投稿処理の前に自動でテストが実行されます。
