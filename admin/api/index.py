"""管理画面（スタッフ向けWeb画面）のバックエンド。

すべてのデータはこのリポジトリの data/ 配下のJSONファイルと画像ファイルとして、
GitHub Contents API経由で直接読み書きする（データベースは使わない）。
画面側にはAPI・JSON・パラメータ等の専門用語を一切出さない前提のため、
このファイルのエラーメッセージもすべて平易な日本語にしてある。

【重要】VercelのPython実行環境では、vercel.jsonのrewriteを使っても
Flaskが受け取るリクエストパスは実際のURL（例: /api/materials）ではなく、
常にrewrite先のパス（/api/index）になってしまう（実機で確認済み）。
そのため、パスではなくクエリパラメータ（resource, id）でどの処理を行うか
振り分ける方式にしている。
"""
from __future__ import annotations

import base64
import binascii
import io
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Vercelのランタイムがこのファイルを読み込む際、同じフォルダ内のモジュールを
# importできるとは限らないため、明示的にこのファイルの場所をパスに追加しておく。
sys.path.insert(0, str(Path(__file__).resolve().parent))
# rise_sns パッケージ（画像生成・キャプション合成等、GitHub Actionsのバッチ処理と共通のロジック）は
# admin/ 直下にある（Vercelのビルド範囲=Root Directory=adminに収める必要があるため、
# リポジトリ直下のsrc/ではなくここに置いている）。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

from flask import Flask, jsonify, request, session
from PIL import Image

import github_client
import user_store
from github_client import GithubClientError
from user_store import UserStoreError
from rise_sns import caption_overlay, decorations, image_generator, platform_formats, selector, text_template

app = Flask(__name__)
app.json.ensure_ascii = False
# セッションの署名に使う鍵。Vercelの環境変数 FLASK_SECRET_KEY として設定する。
# 空文字列は「安全でない既定鍵」として黙って使われてしまう（Flaskはstrなら何でも受け付ける）ため、
# 未設定の場合は明示的にNoneにしておく。Noneならログイン時にFlask側が例外を出して停止するため、
# 「未設定のまま安全でない状態で動いてしまう」事故を防げる。
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or None
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
)

MATERIALS_PATH = "data/materials.json"
TEXTS_PATH = "data/texts.json"
CONFIG_PATH = "data/config.json"
DECORATIONS_PATH = "data/decorations.json"

DEFAULT_CONFIG = {
    "room_types": [
        {"name": "Type A", "bed_size": "上段Wide-Double 155cm×200cm / 下段Semi-Double 140cm×200cm", "max_guests": 10},
        {"name": "Type B", "bed_size": "上段Wide-Double 155cm×200cm / 下段King 185cm×200cm", "max_guests": 8},
        {"name": "Type C", "bed_size": "上段Wide-Double 155cm×200cm / 下段Wide-Double 155cm×200cm", "max_guests": 8},
        {"name": "スイートルーム", "bed_size": "Queen 180cm×200cm×8台", "max_guests": 16},
        {"name": "ツインベッドルーム", "bed_size": "Queen 180cm×200cm×2台", "max_guests": 4},
        {"name": "ダブルベッドルーム", "bed_size": "Double 140cm×200cm×2台", "max_guests": 3},
    ],
    "seasons": ["春", "夏", "秋", "冬", "通年"],
    "text_categories": ["通常訴求", "季節限定", "イベント"],
    "platforms": ["x", "instagram", "facebook", "google"],
    "decoration_placements": [
        "top_left",
        "top_right",
        "top_center",
        "bottom_left",
        "bottom_right",
        "bottom_center",
    ],
}


def _parse_material_ids(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _parse_tags(raw) -> list[str]:
    """カンマ区切りの文字列、または配列の両方を受け付けて、空白除去済みのリストにする。"""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        items = raw.split(",")
    else:
        items = []
    return [item.strip() for item in items if item and item.strip()]

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.*)$", re.DOTALL)
_MIME_TO_EXT = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _decode_image(image_base64: str):
    match = _DATA_URL_RE.match(image_base64 or "")
    if not match:
        raise ValueError("画像データの形式が正しくありません。")
    mime = match.group("mime")
    ext = _MIME_TO_EXT.get(mime, "jpg")
    try:
        raw = base64.b64decode(match.group("data"))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("画像データの読み込みに失敗しました。") from exc
    return raw, ext


@app.errorhandler(GithubClientError)
def _handle_github_error(exc: GithubClientError):
    return _error(str(exc) or "保存に失敗しました。もう一度お試しください。", 502)


@app.errorhandler(UserStoreError)
def _handle_user_store_error(exc: UserStoreError):
    return _error(str(exc) or "認証処理に失敗しました。", 502)


# ---------------------------------------------------------------------------
# 認証（ログイン・ログアウト・初期設定・ユーザー管理）
# ---------------------------------------------------------------------------

def _current_user():
    email = session.get("email")
    if not email:
        return None
    return {"email": email, "role": session.get("role", "user")}


def _get_bootstrap():
    return jsonify({"needs_setup": not user_store.any_users_exist()})


def _post_bootstrap():
    if user_store.any_users_exist():
        return _error("すでにアカウントが作成されているため、この操作は行えません。", 403)

    body = request.get_json(silent=True) or {}
    try:
        user = user_store.create_user(body.get("email") or "", body.get("password") or "", "admin")
    except UserStoreError as exc:
        return _error(str(exc))

    session.permanent = True
    session["email"] = user["email"]
    session["role"] = user["role"]
    return jsonify({"email": user["email"], "role": user["role"]}), 201


def _post_login():
    body = request.get_json(silent=True) or {}
    email = body.get("email") or ""
    password = body.get("password") or ""

    user = user_store.verify_password(email, password)
    if not user:
        return _error("メールアドレスまたはパスワードが正しくありません。", 401)

    session.permanent = True
    session["email"] = user["email"]
    session["role"] = user["role"]
    return jsonify(user)


def _post_logout():
    session.clear()
    return jsonify({"ok": True})


def _get_session_status():
    user = _current_user()
    if not user:
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, "email": user["email"], "role": user["role"]})


def _list_users():
    return jsonify({"users": user_store.list_users()})


def _create_user():
    body = request.get_json(silent=True) or {}
    try:
        user = user_store.create_user(
            body.get("email") or "",
            body.get("password") or "",
            body.get("role") or "user",
        )
    except UserStoreError as exc:
        return _error(str(exc))
    return jsonify(user), 201


def _delete_user(email: str, current_user: dict):
    if current_user["email"] == email.strip().lower():
        return _error("自分自身のアカウントは削除できません。別の管理者に依頼してください。", 400)
    try:
        user_store.delete_user(email)
    except UserStoreError as exc:
        return _error(str(exc), 404)
    return jsonify({"users": user_store.list_users()})


# ---------------------------------------------------------------------------
# 設定（タグの選択肢）
# ---------------------------------------------------------------------------

def _get_config():
    return jsonify(github_client.get_json(CONFIG_PATH, DEFAULT_CONFIG))


# ---------------------------------------------------------------------------
# 部屋タイプ（名前・ベッドサイズ・最大宿泊人数の表記。投稿文言のプレースホルダーが参照する）
# ---------------------------------------------------------------------------

def _list_room_types():
    config_data = github_client.get_json(CONFIG_PATH, DEFAULT_CONFIG)
    return jsonify({"room_types": config_data.get("room_types", [])})


def _create_room_type():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return _error("部屋タイプの名前を入力してください。")
    record = {
        "name": name,
        "bed_size": (body.get("bed_size") or "").strip(),
        "max_guests": (body.get("max_guests") or "").strip(),
    }

    def _mutate(data):
        room_types = data.setdefault("room_types", [])
        if any(rt.get("name") == name for rt in room_types):
            raise ValueError("同じ名前の部屋タイプがすでに登録されています。")
        room_types.append(record)
        return data

    try:
        github_client.update_json_with_retry(
            CONFIG_PATH, _mutate, message=f"add room type {name}", default=DEFAULT_CONFIG
        )
    except ValueError as exc:
        return _error(str(exc))

    return jsonify(record), 201


def _rename_room_type_in_materials(old_name: str, new_name: str):
    def _mutate(data):
        for m in data.setdefault("materials", []):
            if m.get("room_type") == old_name:
                m["room_type"] = new_name
                m["updated_at"] = _now()
        return data

    github_client.update_json_with_retry(
        MATERIALS_PATH,
        _mutate,
        message=f"rename room type {old_name} -> {new_name} in materials",
        default={"materials": []},
    )


def _update_room_type(original_name: str):
    body = request.get_json(silent=True) or {}
    rename_info: dict = {}

    def _mutate(data):
        room_types = data.setdefault("room_types", [])
        target = next((rt for rt in room_types if rt.get("name") == original_name), None)
        if not target:
            raise KeyError("対象の部屋タイプが見つかりませんでした。")
        if "name" in body:
            new_name = (body["name"] or "").strip()
            if not new_name:
                raise ValueError("部屋タイプの名前を入力してください。")
            if new_name != original_name:
                if any(rt.get("name") == new_name for rt in room_types):
                    raise ValueError("同じ名前の部屋タイプがすでに登録されています。")
                rename_info["from"] = original_name
                rename_info["to"] = new_name
            target["name"] = new_name
        if "bed_size" in body:
            target["bed_size"] = (body["bed_size"] or "").strip()
        if "max_guests" in body:
            target["max_guests"] = (body["max_guests"] or "").strip()
        return data

    try:
        new_data = github_client.update_json_with_retry(
            CONFIG_PATH, _mutate, message=f"update room type {original_name}", default=DEFAULT_CONFIG
        )
    except KeyError as exc:
        return _error(str(exc).strip('"'), 404)
    except ValueError as exc:
        return _error(str(exc))

    if rename_info:
        _rename_room_type_in_materials(rename_info["from"], rename_info["to"])

    current_name = body.get("name", original_name) or original_name
    current_name = current_name.strip() if isinstance(current_name, str) else original_name
    updated = next((rt for rt in new_data["room_types"] if rt.get("name") == current_name), None)
    return jsonify(updated)


def _delete_room_type(name: str):
    materials_data = github_client.get_json(MATERIALS_PATH, {"materials": []})
    if any(m.get("room_type") == name for m in materials_data.get("materials", [])):
        return _error("この部屋タイプを使っている写真があるため削除できません。先に写真側の部屋タイプを変更してください。")

    def _mutate(data):
        room_types = data.setdefault("room_types", [])
        data["room_types"] = [rt for rt in room_types if rt.get("name") != name]
        return data

    new_data = github_client.update_json_with_retry(
        CONFIG_PATH, _mutate, message=f"delete room type {name}", default=DEFAULT_CONFIG
    )
    return jsonify({"room_types": new_data["room_types"]})


# ---------------------------------------------------------------------------
# 客室写真（素材）
# ---------------------------------------------------------------------------

def _material_with_url(material: dict) -> dict:
    enriched = dict(material)
    enriched["image_url"] = github_client.public_raw_url(f"data/{material['image_path']}")
    return enriched


def _list_materials():
    data = github_client.get_json(MATERIALS_PATH, {"materials": []})
    materials = [_material_with_url(m) for m in data.get("materials", [])]
    materials.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return jsonify({"materials": materials})


def _create_material():
    body = request.get_json(silent=True) or {}
    image_base64 = body.get("image_base64")
    if not image_base64:
        return _error("写真が選択されていません。")

    try:
        image_bytes, ext = _decode_image(image_base64)
    except ValueError as exc:
        return _error(str(exc))

    material_id = uuid.uuid4().hex[:12]
    image_path = f"images/{material_id}.{ext}"

    github_client.put_file(
        f"data/{image_path}",
        image_bytes,
        message=f"add material image {material_id}",
    )

    record = {
        "id": material_id,
        "image_path": image_path,
        "room_type": body.get("room_type") or "",
        "room_number": (body.get("room_number") or "").strip(),
        "seasons": body.get("seasons") or [],
        "ready_made": bool(body.get("ready_made")),
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }

    def _mutate(data):
        data.setdefault("materials", []).append(record)
        return data

    github_client.update_json_with_retry(
        MATERIALS_PATH, _mutate, message=f"add material {material_id}", default={"materials": []}
    )

    return jsonify(_material_with_url(record)), 201


def _update_material(material_id: str):
    body = request.get_json(silent=True) or {}

    def _mutate(data):
        materials = data.setdefault("materials", [])
        for m in materials:
            if m.get("id") == material_id:
                if "room_type" in body:
                    m["room_type"] = body["room_type"]
                if "room_number" in body:
                    m["room_number"] = (body["room_number"] or "").strip()
                if "seasons" in body:
                    m["seasons"] = body["seasons"]
                if "ready_made" in body:
                    m["ready_made"] = bool(body["ready_made"])
                if "active" in body:
                    m["active"] = bool(body["active"])
                m["updated_at"] = _now()
                return data
        raise ValueError("対象の写真が見つかりませんでした。")

    try:
        new_data = github_client.update_json_with_retry(
            MATERIALS_PATH, _mutate, message=f"update material {material_id}", default={"materials": []}
        )
    except ValueError as exc:
        return _error(str(exc), 404)

    updated = next((m for m in new_data["materials"] if m["id"] == material_id), None)
    return jsonify(_material_with_url(updated))


def _delete_material(material_id: str):
    holder: dict = {}

    def _mutate(data):
        materials = data.setdefault("materials", [])
        remaining = [m for m in materials if m.get("id") != material_id]
        removed = [m for m in materials if m.get("id") == material_id]
        holder["removed"] = removed[0] if removed else None
        data["materials"] = remaining
        return data

    new_data = github_client.update_json_with_retry(
        MATERIALS_PATH, _mutate, message=f"delete material {material_id}", default={"materials": []}
    )

    removed = holder.get("removed")
    if removed:
        github_client.delete_file(f"data/{removed['image_path']}", message=f"delete material image {material_id}")

    return jsonify({"materials": [_material_with_url(m) for m in new_data["materials"]]})


# ---------------------------------------------------------------------------
# 投稿文言・キーワード
# ---------------------------------------------------------------------------

def _list_texts():
    data = github_client.get_json(TEXTS_PATH, {"texts": []})
    texts = data.get("texts", [])
    texts.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return jsonify({"texts": texts})


def _create_text():
    body = request.get_json(silent=True) or {}
    text_value = (body.get("text") or "").strip()
    if not text_value:
        return _error("文言が入力されていません。")

    text_id = uuid.uuid4().hex[:12]
    record = {
        "id": text_id,
        "text": text_value,
        "category": body.get("category") or "",
        "tags": _parse_tags(body.get("tags")),
        "material_ids": _parse_material_ids(body.get("material_ids")),
        "platforms": {
            "x": bool((body.get("platforms") or {}).get("x")),
            "instagram": bool((body.get("platforms") or {}).get("instagram")),
            "facebook": bool((body.get("platforms") or {}).get("facebook")),
            "google": bool((body.get("platforms") or {}).get("google")),
        },
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }

    def _mutate(data):
        data.setdefault("texts", []).append(record)
        return data

    github_client.update_json_with_retry(TEXTS_PATH, _mutate, message=f"add text {text_id}", default={"texts": []})

    return jsonify(record), 201


def _update_text(text_id: str):
    body = request.get_json(silent=True) or {}

    def _mutate(data):
        texts = data.setdefault("texts", [])
        for t in texts:
            if t.get("id") == text_id:
                if "text" in body:
                    t["text"] = (body["text"] or "").strip()
                if "category" in body:
                    t["category"] = body["category"]
                if "tags" in body:
                    t["tags"] = _parse_tags(body["tags"])
                if "material_ids" in body:
                    t["material_ids"] = _parse_material_ids(body["material_ids"])
                if "platforms" in body:
                    platforms = body["platforms"] or {}
                    t["platforms"] = {
                        "x": bool(platforms.get("x")),
                        "instagram": bool(platforms.get("instagram")),
                        "facebook": bool(platforms.get("facebook")),
                        "google": bool(platforms.get("google")),
                    }
                if "active" in body:
                    t["active"] = bool(body["active"])
                t["updated_at"] = _now()
                return data
        raise ValueError("対象の文言が見つかりませんでした。")

    try:
        new_data = github_client.update_json_with_retry(
            TEXTS_PATH, _mutate, message=f"update text {text_id}", default={"texts": []}
        )
    except ValueError as exc:
        return _error(str(exc), 404)

    updated = next((t for t in new_data["texts"] if t["id"] == text_id), None)
    return jsonify(updated)


def _delete_text(text_id: str):
    def _mutate(data):
        texts = data.setdefault("texts", [])
        data["texts"] = [t for t in texts if t.get("id") != text_id]
        return data

    new_data = github_client.update_json_with_retry(
        TEXTS_PATH, _mutate, message=f"delete text {text_id}", default={"texts": []}
    )
    return jsonify({"texts": new_data["texts"]})


# ---------------------------------------------------------------------------
# スタンプ・ハッシュタグ画像
# ---------------------------------------------------------------------------

def _decoration_with_url(decoration: dict) -> dict:
    enriched = dict(decoration)
    enriched["image_url"] = github_client.public_raw_url(f"data/{decoration['image_path']}")
    return enriched


def _list_decorations():
    data = github_client.get_json(DECORATIONS_PATH, {"decorations": []})
    items = [_decoration_with_url(d) for d in data.get("decorations", [])]
    items.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return jsonify({"decorations": items})


def _create_decoration():
    body = request.get_json(silent=True) or {}
    image_base64 = body.get("image_base64")
    if not image_base64:
        return _error("画像が選択されていません。")

    placement = body.get("placement")
    if placement not in DEFAULT_CONFIG["decoration_placements"]:
        return _error("表示位置を選択してください。")

    try:
        image_bytes, ext = _decode_image(image_base64)
    except ValueError as exc:
        return _error(str(exc))

    decoration_id = uuid.uuid4().hex[:12]
    image_path = f"decorations/{decoration_id}.{ext}"

    github_client.put_file(
        f"data/{image_path}",
        image_bytes,
        message=f"add decoration image {decoration_id}",
    )

    record = {
        "id": decoration_id,
        "image_path": image_path,
        "name": (body.get("name") or "").strip(),
        "tags": _parse_tags(body.get("tags")),
        "placement": placement,
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }

    def _mutate(data):
        data.setdefault("decorations", []).append(record)
        return data

    github_client.update_json_with_retry(
        DECORATIONS_PATH, _mutate, message=f"add decoration {decoration_id}", default={"decorations": []}
    )

    return jsonify(_decoration_with_url(record)), 201


def _update_decoration(decoration_id: str):
    body = request.get_json(silent=True) or {}

    def _mutate(data):
        items = data.setdefault("decorations", [])
        for d in items:
            if d.get("id") == decoration_id:
                if "name" in body:
                    d["name"] = (body["name"] or "").strip()
                if "tags" in body:
                    d["tags"] = _parse_tags(body["tags"])
                if "placement" in body:
                    if body["placement"] not in DEFAULT_CONFIG["decoration_placements"]:
                        raise ValueError("表示位置の指定が正しくありません。")
                    d["placement"] = body["placement"]
                if "active" in body:
                    d["active"] = bool(body["active"])
                d["updated_at"] = _now()
                return data
        raise ValueError("対象のスタンプが見つかりませんでした。")

    try:
        new_data = github_client.update_json_with_retry(
            DECORATIONS_PATH, _mutate, message=f"update decoration {decoration_id}", default={"decorations": []}
        )
    except ValueError as exc:
        return _error(str(exc), 404)

    updated = next((d for d in new_data["decorations"] if d["id"] == decoration_id), None)
    return jsonify(_decoration_with_url(updated))


def _delete_decoration(decoration_id: str):
    holder: dict = {}

    def _mutate(data):
        items = data.setdefault("decorations", [])
        remaining = [d for d in items if d.get("id") != decoration_id]
        removed = [d for d in items if d.get("id") == decoration_id]
        holder["removed"] = removed[0] if removed else None
        data["decorations"] = remaining
        return data

    new_data = github_client.update_json_with_retry(
        DECORATIONS_PATH, _mutate, message=f"delete decoration {decoration_id}", default={"decorations": []}
    )

    removed = holder.get("removed")
    if removed:
        github_client.delete_file(f"data/{removed['image_path']}", message=f"delete decoration image {decoration_id}")

    return jsonify({"decorations": [_decoration_with_url(d) for d in new_data["decorations"]]})


# ---------------------------------------------------------------------------
# プレビュー（実際にAI画像生成を行い、SNSごとの見た目を事前に確認する）
# ---------------------------------------------------------------------------

def _open_image_from_repo(image_path: str) -> Image.Image:
    content, _ = github_client.get_file(f"data/{image_path}")
    if content is None:
        raise ValueError("画像データが見つかりませんでした。")
    return Image.open(io.BytesIO(content))


def _image_to_data_url(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _create_preview():
    body = request.get_json(silent=True) or {}
    material_id = body.get("material_id")
    text_id = body.get("text_id")
    if not material_id or not text_id:
        return _error("写真と文言を選んでください。")

    materials_data = github_client.get_json(MATERIALS_PATH, {"materials": []})
    material = next((m for m in materials_data.get("materials", []) if m.get("id") == material_id), None)
    if not material:
        return _error("対象の写真が見つかりませんでした。", 404)

    texts_data = github_client.get_json(TEXTS_PATH, {"texts": []})
    text = next((t for t in texts_data.get("texts", []) if t.get("id") == text_id), None)
    if not text:
        return _error("対象の文言が見つかりませんでした。", 404)

    platforms = [p for p, enabled in (text.get("platforms") or {}).items() if enabled]
    if not platforms:
        return _error("この文言には投稿先のSNSが選択されていません。")

    try:
        room_photo = _open_image_from_repo(material["image_path"])
    except ValueError as exc:
        return _error(str(exc), 404)

    config_data = github_client.get_json(CONFIG_PATH, DEFAULT_CONFIG)
    room_type_defs = text_template.room_types_by_name(config_data)
    rendered_text = text_template.render_text(text["text"], material, room_type_defs)

    if material.get("ready_made"):
        # すでに人物が入った完成写真の場合は、AIでの合成をせずそのまま使う（本番投稿と同じ挙動）。
        generated = room_photo
    else:
        try:
            generated = image_generator.generate_composite_image(room_photo, rendered_text)
        except image_generator.ImageGenerationError as exc:
            return _error(f"画像の生成に失敗しました: {exc}", 502)

    try:
        captioned = caption_overlay.add_caption(generated, rendered_text)
    except FileNotFoundError as exc:
        return _error(f"文言の合成に失敗しました: {exc}", 502)

    creative_tags = selector.compute_creative_tags(material, text)
    decorations_data = github_client.get_json(DECORATIONS_PATH, {"decorations": []})
    matched_decorations = decorations.select_decorations(decorations_data.get("decorations", []), creative_tags)

    def _open_stamp(decoration):
        return _open_image_from_repo(decoration["image_path"])

    images = {}
    for platform in platforms:
        rendered = platform_formats.render_for_platform(captioned, platform)
        if matched_decorations:
            rendered = decorations.apply_decorations(rendered, matched_decorations, open_stamp=_open_stamp)
        images[platform] = _image_to_data_url(rendered)

    return jsonify({"images": images, "rendered_text": rendered_text})


# ---------------------------------------------------------------------------
# ルーティング（唯一のエンドポイント。resource/idクエリパラメータで振り分ける）
# ---------------------------------------------------------------------------

@app.route("/api/index", methods=["GET", "POST", "PUT", "DELETE"])
def api_entry():
    resource = request.args.get("resource")
    item_id = request.args.get("id")
    method = request.method

    # ログイン前でもアクセスできるリソース（初期設定・ログイン・ログイン状態確認）
    if resource == "bootstrap":
        if method == "GET":
            return _get_bootstrap()
        if method == "POST":
            return _post_bootstrap()
        return _error("不明なリクエストです。", 404)

    if resource == "login" and method == "POST":
        return _post_login()

    if resource == "logout" and method == "POST":
        return _post_logout()

    if resource == "session" and method == "GET":
        return _get_session_status()

    # ここから先はログインが必要
    current_user = _current_user()
    if not current_user:
        return _error("ログインが必要です。もう一度ログインしてください。", 401)

    if resource == "users":
        if current_user["role"] != "admin":
            return _error("この操作には管理者権限が必要です。", 403)
        if method == "GET":
            return _list_users()
        if method == "POST":
            return _create_user()
        if method == "DELETE" and item_id:
            return _delete_user(item_id, current_user)
        return _error("不明なリクエストです。", 404)

    if resource == "config" and method == "GET":
        return _get_config()

    if resource == "room_types":
        if method == "GET":
            return _list_room_types()
        if method == "POST":
            return _create_room_type()
        if method == "PUT" and item_id:
            return _update_room_type(item_id)
        if method == "DELETE" and item_id:
            return _delete_room_type(item_id)

    if resource == "materials":
        if method == "GET":
            return _list_materials()
        if method == "POST":
            return _create_material()
        if method == "PUT" and item_id:
            return _update_material(item_id)
        if method == "DELETE" and item_id:
            return _delete_material(item_id)

    if resource == "texts":
        if method == "GET":
            return _list_texts()
        if method == "POST":
            return _create_text()
        if method == "PUT" and item_id:
            return _update_text(item_id)
        if method == "DELETE" and item_id:
            return _delete_text(item_id)

    if resource == "decorations":
        if method == "GET":
            return _list_decorations()
        if method == "POST":
            return _create_decoration()
        if method == "PUT" and item_id:
            return _update_decoration(item_id)
        if method == "DELETE" and item_id:
            return _delete_decoration(item_id)

    if resource == "preview" and method == "POST":
        return _create_preview()

    return _error("不明なリクエストです。", 404)
