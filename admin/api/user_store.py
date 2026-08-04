"""管理画面にログインするユーザーアカウント（メールアドレス・パスワードのハッシュ値・権限）を
Upstash Redis（Vercel Marketplace経由で接続）に保存する。

GitHubリポジトリはGitの性質上、パスワードを変更・ユーザーを削除しても古いハッシュ値が
コミット履歴に残り続けてしまうため、認証情報だけはこちら（Upstash Redis）に保存する。
Vercelダッシュボードの Storage → Marketplace で Upstash を追加しプロジェクトに接続すると、
UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN が自動的に環境変数として注入される。
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import requests
from werkzeug.security import check_password_hash, generate_password_hash

USERS_SET_KEY = "users"
MIN_PASSWORD_LENGTH = 8
VALID_ROLES = ("admin", "user")


class UserStoreError(RuntimeError):
    """スタッフ向けには平易なメッセージとして表示される想定のエラー。"""


def _rest_url() -> str:
    # VercelのStorage画面からUpstash(Redis)を接続すると、実際には KV_REST_API_URL という
    # 名前で環境変数が注入される（Upstash公式の UPSTASH_REDIS_REST_URL という名前ではない）。
    # 将来的な名称変更にも耐えられるよう両方を確認する。
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL", "")
    if not url:
        raise UserStoreError("KV_REST_API_URL（Upstashの接続先）が設定されていません。")
    return url.rstrip("/")


def _headers() -> dict:
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
    if not token:
        raise UserStoreError("KV_REST_API_TOKEN（Upstashの認証トークン）が設定されていません。")
    return {"Authorization": f"Bearer {token}"}


def _command(*parts):
    """UpstashへPOSTでコマンドを送る（値をURLに含めず、ログへの流出を避けるため）。"""
    resp = requests.post(_rest_url(), headers=_headers(), json=list(parts), timeout=10)
    if resp.status_code >= 400:
        raise UserStoreError(f"認証データの読み書きに失敗しました（{resp.status_code}）。")
    data = resp.json()
    if data.get("error"):
        raise UserStoreError(f"認証データの読み書きに失敗しました: {data['error']}")
    return data.get("result")


def _pipeline(commands: list[list]):
    """複数コマンドを1回のHTTPリクエストにまとめて送る（ユーザー数が多いときの読み込み遅延を防ぐため）。"""
    if not commands:
        return []
    resp = requests.post(f"{_rest_url()}/pipeline", headers=_headers(), json=commands, timeout=10)
    if resp.status_code >= 400:
        raise UserStoreError(f"認証データの読み書きに失敗しました（{resp.status_code}）。")
    results = resp.json()
    for item in results:
        if isinstance(item, dict) and item.get("error"):
            raise UserStoreError(f"認証データの読み書きに失敗しました: {item['error']}")
    return [item.get("result") if isinstance(item, dict) else item for item in results]


def _user_key(email: str) -> str:
    return f"user:{email.strip().lower()}"


def _fields_to_dict(flat_fields) -> dict:
    flat_fields = flat_fields or []
    return dict(zip(flat_fields[0::2], flat_fields[1::2]))


def any_users_exist() -> bool:
    members = _command("SMEMBERS", USERS_SET_KEY)
    return bool(members)


def get_user(email: str) -> Optional[dict]:
    email = email.strip().lower()
    record = _fields_to_dict(_command("HGETALL", _user_key(email)))
    if not record:
        return None
    return {
        "email": email,
        "password_hash": record.get("password_hash", ""),
        "role": record.get("role", "user"),
        "created_at": record.get("created_at", ""),
    }


def list_users() -> list[dict]:
    emails = _command("SMEMBERS", USERS_SET_KEY) or []
    if not emails:
        return []

    # ユーザーごとに個別リクエストを送ると人数分だけ往復が発生し読み込みが遅くなるため、
    # 1回のパイプライン呼び出しにまとめて送る。
    results = _pipeline([["HGETALL", _user_key(email)] for email in emails])

    users = []
    for email, flat_fields in zip(emails, results):
        record = _fields_to_dict(flat_fields)
        if not record:
            continue
        users.append(
            {
                "email": email.strip().lower(),
                "role": record.get("role", "user"),
                "created_at": record.get("created_at", ""),
            }
        )
    users.sort(key=lambda u: u["created_at"])
    return users


def create_user(email: str, password: str, role: str) -> dict:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise UserStoreError("メールアドレスの形式が正しくありません。")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise UserStoreError(f"パスワードは{MIN_PASSWORD_LENGTH}文字以上にしてください。")
    if role not in VALID_ROLES:
        raise UserStoreError("権限の指定が正しくありません。")
    if get_user(email):
        raise UserStoreError("そのメールアドレスはすでに登録されています。")

    password_hash = generate_password_hash(password)
    created_at = datetime.now(timezone.utc).isoformat()

    _command(
        "HSET", _user_key(email),
        "password_hash", password_hash,
        "role", role,
        "created_at", created_at,
    )
    _command("SADD", USERS_SET_KEY, email)

    return {"email": email, "role": role, "created_at": created_at}


def update_user(email: str, role: Optional[str] = None, new_password: Optional[str] = None) -> dict:
    """権限の変更・パスワードの再設定を行う（管理画面の「編集する」から呼ばれる）。"""
    email = email.strip().lower()
    user = get_user(email)
    if not user:
        raise UserStoreError("対象のユーザーが見つかりませんでした。")

    if role is not None:
        if role not in VALID_ROLES:
            raise UserStoreError("権限の指定が正しくありません。")
        if user["role"] == "admin" and role != "admin":
            remaining_admins = [u for u in list_users() if u["role"] == "admin" and u["email"] != email]
            if not remaining_admins:
                raise UserStoreError("最後の管理者アカウントの権限は変更できません。")
        _command("HSET", _user_key(email), "role", role)

    if new_password is not None:
        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise UserStoreError(f"パスワードは{MIN_PASSWORD_LENGTH}文字以上にしてください。")
        _command("HSET", _user_key(email), "password_hash", generate_password_hash(new_password))

    updated = get_user(email)
    return {"email": updated["email"], "role": updated["role"], "created_at": updated["created_at"]}


def delete_user(email: str) -> None:
    email = email.strip().lower()
    user = get_user(email)
    if not user:
        raise UserStoreError("対象のユーザーが見つかりませんでした。")

    if user["role"] == "admin":
        remaining_admins = [u for u in list_users() if u["role"] == "admin" and u["email"] != email]
        if not remaining_admins:
            raise UserStoreError("最後の管理者アカウントは削除できません。")

    _command("DEL", _user_key(email))
    _command("SREM", USERS_SET_KEY, email)


def verify_password(email: str, password: str) -> Optional[dict]:
    user = get_user(email)
    if not user or not user.get("password_hash"):
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return {"email": user["email"], "role": user["role"]}
