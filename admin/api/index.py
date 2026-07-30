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
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Vercelのランタイムがこのファイルを読み込む際、同じフォルダ内のモジュールを
# importできるとは限らないため、明示的にこのファイルの場所をパスに追加しておく。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, request

import github_client
from github_client import GithubClientError

app = Flask(__name__)
app.json.ensure_ascii = False

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


# ---------------------------------------------------------------------------
# 設定（タグの選択肢）
# ---------------------------------------------------------------------------

def _get_config():
    return jsonify(github_client.get_json(CONFIG_PATH, DEFAULT_CONFIG))


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
# ルーティング（唯一のエンドポイント。resource/idクエリパラメータで振り分ける）
# ---------------------------------------------------------------------------

@app.route("/api/index", methods=["GET", "POST", "PUT", "DELETE"])
def api_entry():
    resource = request.args.get("resource")
    item_id = request.args.get("id")
    method = request.method

    if resource == "config" and method == "GET":
        return _get_config()

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

    return _error("不明なリクエストです。", 404)
