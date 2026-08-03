import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))

import index  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)

    state = {"config": {"room_types": []}}

    def fake_get_json(path, default):
        if path == index.CONFIG_PATH:
            return state["config"]
        return default

    def fake_update_json_with_retry(path, mutate_fn, message, default, retries=2):
        if path == index.CONFIG_PATH:
            state["config"] = mutate_fn(state["config"])
            return state["config"]
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(index.github_client, "get_json", fake_get_json)
    monkeypatch.setattr(index.github_client, "update_json_with_retry", fake_update_json_with_retry)

    fake_client = index.app.test_client()
    with fake_client.session_transaction() as sess:
        sess["email"] = "staff@example.com"
        sess["role"] = "user"

    return fake_client, state


def test_get_config_fills_in_default_text_styles_when_missing(client):
    fake_client, _ = client
    resp = fake_client.get("/api/index?resource=config")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["text_styles"]) == 1
    assert body["text_styles"][0]["is_default"] is True
    assert "font_weights" in body


def test_list_text_styles_returns_default_entry_when_none_saved(client):
    fake_client, _ = client
    resp = fake_client.get("/api/index?resource=text_styles")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["text_styles"]) == 1
    assert body["text_styles"][0]["name"] == "デフォルト"


def test_create_text_style(client):
    fake_client, state = client
    resp = fake_client.post(
        "/api/index?resource=text_styles",
        json={"name": "オレンジ", "badge_bg_color": "#112233", "badge_weight": "bold"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "オレンジ"
    assert body["badge_bg_color"] == "#112233"
    assert body["is_default"] is False
    # 既定値の項目も自動的に補われること
    assert body["body_weight"] == "medium"

    names = [s["name"] for s in state["config"]["text_styles"]]
    assert "デフォルト" in names
    assert "オレンジ" in names


def test_create_text_style_requires_name(client):
    fake_client, _ = client
    resp = fake_client.post("/api/index?resource=text_styles", json={"badge_bg_color": "#112233"})
    assert resp.status_code == 400


def test_create_text_style_rejects_invalid_color(client):
    fake_client, _ = client
    resp = fake_client.post("/api/index?resource=text_styles", json={"name": "テスト", "badge_bg_color": "not-a-color"})
    assert resp.status_code == 400


def test_create_text_style_rejects_invalid_weight(client):
    fake_client, _ = client
    resp = fake_client.post("/api/index?resource=text_styles", json={"name": "テスト", "badge_weight": "ultra"})
    assert resp.status_code == 400


def test_update_text_style_saves_fields(client):
    fake_client, state = client
    create_resp = fake_client.post("/api/index?resource=text_styles", json={"name": "オレンジ"})
    style_id = create_resp.get_json()["id"]

    resp = fake_client.put(f"/api/index?resource=text_styles&id={style_id}", json={"badge_bg_color": "#445566"})
    assert resp.status_code == 200
    assert resp.get_json()["badge_bg_color"] == "#445566"


def test_update_text_style_can_set_default(client):
    fake_client, state = client
    create_resp = fake_client.post("/api/index?resource=text_styles", json={"name": "オレンジ"})
    style_id = create_resp.get_json()["id"]

    resp = fake_client.put(f"/api/index?resource=text_styles&id={style_id}", json={"set_default": True})
    assert resp.status_code == 200
    assert resp.get_json()["is_default"] is True

    styles = state["config"]["text_styles"]
    default_ids = [s["id"] for s in styles if s.get("is_default")]
    assert default_ids == [style_id]


def test_update_text_style_not_found(client):
    fake_client, _ = client
    resp = fake_client.put("/api/index?resource=text_styles&id=does-not-exist", json={"badge_bg_color": "#112233"})
    assert resp.status_code == 404


def test_delete_text_style_reassigns_default_when_needed(client):
    fake_client, state = client
    create_resp = fake_client.post("/api/index?resource=text_styles", json={"name": "オレンジ"})
    style_id = create_resp.get_json()["id"]
    fake_client.put(f"/api/index?resource=text_styles&id={style_id}", json={"set_default": True})

    resp = fake_client.delete(f"/api/index?resource=text_styles&id={style_id}")
    assert resp.status_code == 200
    remaining = resp.get_json()["text_styles"]
    assert len(remaining) == 1
    assert remaining[0]["is_default"] is True


def test_delete_text_style_blocks_removing_the_last_one(client):
    fake_client, _ = client
    resp = fake_client.delete(f"/api/index?resource=text_styles&id={index.text_style_helper.DEFAULT_STYLE_ID}")
    assert resp.status_code == 400


def test_text_styles_requires_login(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)
    anonymous_client = index.app.test_client()
    resp = anonymous_client.get("/api/index?resource=text_styles")
    assert resp.status_code == 401
