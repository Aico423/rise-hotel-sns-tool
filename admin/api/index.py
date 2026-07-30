"""管理画面（スタッフ向けWeb画面）のバックエンド。

すべてのデータはこのリポジトリの data/ 配下のJSONファイルと画像ファイルとして、
GitHub Contents API経由で直接読み書きする（データベースは使わない）。
画面側にはAPI・JSON・パラメータ等の専門用語を一切出さない前提のため、
このファイルのエラーメッセージもすべて平易な日本語にしてある。
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

DEFAULT_CONFIG = {
    "room_types": ["シングル", "ダブル", "ツイン", "スイート"],
    "seasons": ["春", "夏", "秋", "冬", "通年"],
    "features": ["夜景あり", "和室", "広め", "その他"],
    "text_categories": ["通常訴求", "季節限定", "イベント"],
    "platforms": ["x", "instagram", "facebook", "google"],
}

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


@app.route("/", defaults={"_catchall": ""})
@app.route("/<path:_catchall>")
def debug_path(_catchall):
    return jsonify(
        {
            "path": request.path,
            "full_path": request.full_path,
            "script_root": request.script_root,
            "base_url": request.base_url,
            "environ_PATH_INFO": request.environ.get("PATH_INFO"),
            "environ_SCRIPT_NAME": request.environ.get("SCRIPT_NAME"),
        }
    )


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(github_client.get_json(CONFIG_PATH, DEFAULT_CONFIG))


# ---------------------------------------------------------------------------
# 客室写真（素材）
# ---------------------------------------------------------------------------

def _material_with_url(material: dict) -> dict:
    enriched = dict(material)
    enriched["image_url"] = github_client.public_raw_url(f"data/{material['image_path']}")
    return enriched


@app.route("/api/materials", methods=["GET"])
def list_materials():
    data = github_client.get_json(MATERIALS_PATH, {"materials": []})
    materials = [_material_with_url(m) for m in data.get("materials", [])]
    materials.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return jsonify({"materials": materials})


@app.route("/api/materials", methods=["POST"])
def create_material():
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
        "seasons": body.get("seasons") or [],
        "features": body.get("features") or [],
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


@app.route("/api/materials/<material_id>", methods=["PUT"])
def update_material(material_id: str):
    body = request.get_json(silent=True) or {}

    def _mutate(data):
        materials = data.setdefault("materials", [])
        for m in materials:
            if m.get("id") == material_id:
                if "room_type" in body:
                    m["room_type"] = body["room_type"]
                if "seasons" in body:
                    m["seasons"] = body["seasons"]
                if "features" in body:
                    m["features"] = body["features"]
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


@app.route("/api/materials/<material_id>", methods=["DELETE"])
def delete_material(material_id: str):
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

@app.route("/api/texts", methods=["GET"])
def list_texts():
    data = github_client.get_json(TEXTS_PATH, {"texts": []})
    texts = data.get("texts", [])
    texts.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return jsonify({"texts": texts})


@app.route("/api/texts", methods=["POST"])
def create_text():
    body = request.get_json(silent=True) or {}
    text_value = (body.get("text") or "").strip()
    if not text_value:
        return _error("文言が入力されていません。")

    text_id = uuid.uuid4().hex[:12]
    record = {
        "id": text_id,
        "text": text_value,
        "category": body.get("category") or "",
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


@app.route("/api/texts/<text_id>", methods=["PUT"])
def update_text(text_id: str):
    body = request.get_json(silent=True) or {}

    def _mutate(data):
        texts = data.setdefault("texts", [])
        for t in texts:
            if t.get("id") == text_id:
                if "text" in body:
                    t["text"] = (body["text"] or "").strip()
                if "category" in body:
                    t["category"] = body["category"]
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


@app.route("/api/texts/<text_id>", methods=["DELETE"])
def delete_text(text_id: str):
    def _mutate(data):
        texts = data.setdefault("texts", [])
        data["texts"] = [t for t in texts if t.get("id") != text_id]
        return data

    new_data = github_client.update_json_with_retry(
        TEXTS_PATH, _mutate, message=f"delete text {text_id}", default={"texts": []}
    )
    return jsonify({"texts": new_data["texts"]})
