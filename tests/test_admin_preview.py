import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))

import index  # noqa: E402
from rise_sns import image_generator  # noqa: E402


def _png_bytes(size=(200, 200), color=(120, 120, 120)):
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MATERIAL = {
    "id": "mat-1",
    "image_path": "images/mat-1.jpg",
    "room_type": "Type B",
    "room_number": "601",
    "seasons": ["夏"],
    "ready_made": False,
    "active": True,
}

READY_MADE_MATERIAL = {**MATERIAL, "id": "mat-2", "ready_made": True}

TEXT = {
    "id": "text-1",
    "text": "{room_number}号室 最大{max_guests}名様 {bed_size}",
    "category": "通常訴求",
    "tags": [],
    "material_ids": [],
    "platforms": {"x": True, "instagram": True, "facebook": False, "google": False},
    "active": True,
}

TEXT_NO_PLATFORMS = {**TEXT, "id": "text-2", "platforms": {"x": False, "instagram": False, "facebook": False, "google": False}}

CONFIG = {
    "room_types": [{"name": "Type B", "bed_size": "上段Wide-Double / 下段King", "max_guests": 8}],
}


@pytest.fixture
def client(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)

    fake_client = index.app.test_client()
    with fake_client.session_transaction() as sess:
        sess["email"] = "staff@example.com"
        sess["role"] = "user"

    def fake_get_json(path, default):
        if path == index.MATERIALS_PATH:
            return {"materials": [MATERIAL, READY_MADE_MATERIAL]}
        if path == index.TEXTS_PATH:
            return {"texts": [TEXT, TEXT_NO_PLATFORMS]}
        if path == index.CONFIG_PATH:
            return CONFIG
        if path == index.DECORATIONS_PATH:
            return {"decorations": []}
        return default

    def fake_get_file(path):
        return _png_bytes(), "fake-sha"

    monkeypatch.setattr(index.github_client, "get_json", fake_get_json)
    monkeypatch.setattr(index.github_client, "get_file", fake_get_file)

    return fake_client


def test_preview_requires_material_and_text(client):
    resp = client.post("/api/index?resource=preview", json={})
    assert resp.status_code == 400


def test_preview_generates_images_for_enabled_platforms(client, monkeypatch):
    monkeypatch.setattr(
        index.image_generator,
        "generate_composite_image",
        lambda room_photo, keyword: Image.new("RGB", (800, 600), color=(50, 50, 50)),
    )

    resp = client.post("/api/index?resource=preview", json={"material_id": "mat-1", "text_id": "text-1"})
    assert resp.status_code == 200
    body = resp.get_json()

    assert set(body["images"].keys()) == {"x", "instagram"}
    assert body["images"]["x"].startswith("data:image/jpeg;base64,")
    assert body["rendered_text"] == "601号室 最大8名様 上段Wide-Double / 下段King"


def test_preview_skips_ai_generation_for_ready_made_material(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        index.image_generator,
        "generate_composite_image",
        lambda room_photo, keyword: calls.append(1) or room_photo,
    )

    resp = client.post("/api/index?resource=preview", json={"material_id": "mat-2", "text_id": "text-1"})
    assert resp.status_code == 200
    assert calls == []


def test_preview_returns_error_when_material_missing(client):
    resp = client.post("/api/index?resource=preview", json={"material_id": "does-not-exist", "text_id": "text-1"})
    assert resp.status_code == 404


def test_preview_returns_error_when_text_missing(client):
    resp = client.post("/api/index?resource=preview", json={"material_id": "mat-1", "text_id": "does-not-exist"})
    assert resp.status_code == 404


def test_preview_returns_error_when_no_platforms_enabled(client):
    resp = client.post("/api/index?resource=preview", json={"material_id": "mat-1", "text_id": "text-2"})
    assert resp.status_code == 400


def test_preview_returns_error_when_generation_fails(client, monkeypatch):
    def _raise(room_photo, keyword):
        raise image_generator.ImageGenerationError("テストエラー")

    monkeypatch.setattr(index.image_generator, "generate_composite_image", _raise)

    resp = client.post("/api/index?resource=preview", json={"material_id": "mat-1", "text_id": "text-1"})
    assert resp.status_code == 502


def test_preview_requires_login(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)
    anonymous_client = index.app.test_client()
    resp = anonymous_client.post("/api/index?resource=preview", json={"material_id": "mat-1", "text_id": "text-1"})
    assert resp.status_code == 401
