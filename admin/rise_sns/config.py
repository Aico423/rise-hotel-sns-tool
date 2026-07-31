"""環境変数の読み込みと、プロジェクト全体で使う定数・フィーチャーフラグの定義。

認証情報はすべて環境変数（ローカル実行時は .env、GitHub Actionsでは Secrets）から読み込み、
コードやリポジトリには一切書き込まない。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
CONFIG_PATH = DATA_DIR / "config.json"
MATERIALS_PATH = DATA_DIR / "materials.json"
TEXTS_PATH = DATA_DIR / "texts.json"
POST_HISTORY_PATH = DATA_DIR / "post_history.json"
DECORATIONS_PATH = DATA_DIR / "decorations.json"

# フォントは admin/assets/fonts に置いている（Vercel管理画面のRoot Directoryが
# `admin` に設定されており、それより外側のファイルはVercelのデプロイに含まれないため。
# GitHub Actions側は全リポジトリをcheckoutするので、この場所でも問題なく見つかる）。
FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
CAPTION_FONT_PATH = FONTS_DIR / "NotoSansJP-Bold.ttf"


def env_bool(name: str, default: bool) -> bool:
    """"true"/"1"/"yes" のような文字列を真偽値として読み込む（大小文字を無視）。"""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("true", "1", "yes", "on")


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_str(name: str, default: str) -> str:
    """空文字列（GitHub Actionsで未設定のvarsを展開した場合など）も未設定として扱う。"""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value


# --- リポジトリ情報（生成画像の公開URL組み立て・Actionsからのpush先） ---
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")  # 例: "your-org/rise-hotel-sns-tool"
GITHUB_BRANCH = env_str("GITHUB_BRANCH", "main")

# --- Gemini（画像編集 / 通称 Nano Banana 2） ---
# モデルIDは変更されうるため、この1箇所の定数だけを差し替えれば追随できるようにしてある。
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_IMAGE_MODEL = env_str("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
GEMINI_MAX_RETRIES = env_int("GEMINI_MAX_RETRIES", 3)

# --- X（旧Twitter） ---
X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "")
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")

# --- Meta（Instagram / Facebook） ---
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "")
FACEBOOK_POST_MODE = env_str("FACEBOOK_POST_MODE", "feed")  # "story" or "feed"
META_GRAPH_API_VERSION = env_str("META_GRAPH_API_VERSION", "v21.0")
# Facebookページのストーリー投稿用エンドポイント名は仕様が変わりやすいため環境変数で上書き可能にしてある。
# 実装時点(2026年7月)では未確定。有効化前に必ず最新のGraph APIドキュメントで確認すること。
FACEBOOK_STORY_ENDPOINT = env_str("FACEBOOK_STORY_ENDPOINT", "photo_stories")

# --- Google Business Profile ---
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GOOGLE_BUSINESS_ACCOUNT_ID = os.environ.get("GOOGLE_BUSINESS_ACCOUNT_ID", "")
GOOGLE_BUSINESS_LOCATION_ID = os.environ.get("GOOGLE_BUSINESS_LOCATION_ID", "")

# --- 各プラットフォームの有効/無効フラグ ---
# Meta・Googleは審査待ちのため既定は無効（dry-run）。審査承認後にtrueへ切り替えるだけで本番投稿に切り替わる。
ENABLE_X = env_bool("ENABLE_X", True)
ENABLE_INSTAGRAM = env_bool("ENABLE_INSTAGRAM", False)
ENABLE_FACEBOOK = env_bool("ENABLE_FACEBOOK", False)
ENABLE_GOOGLE_BUSINESS = env_bool("ENABLE_GOOGLE_BUSINESS", False)

# --- 通知 ---
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# --- 素材の重複投稿を避けるために直近何日分の履歴を見るか ---
POST_HISTORY_LOOKBACK_DAYS = env_int("POST_HISTORY_LOOKBACK_DAYS", 14)

# --- 生成画像の品質チェックしきい値 ---
MIN_IMAGE_DIMENSION = env_int("MIN_IMAGE_DIMENSION", 512)
BLANK_IMAGE_STDDEV_THRESHOLD = 3.0
