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


def test_get_config_fills_in_default_text_style_when_missing(client):
    fake_client, _ = client
    resp = fake_client.get("/api/index?resource=config")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["text_style"]["badge_weight"] == "extrabold"
    assert "font_weights" in body


def test_update_text_style_saves_valid_fields(client):
    fake_client, state = client
    resp = fake_client.put(
        "/api/index?resource=text_style",
        json={"badge_bg_color": "#112233", "badge_weight": "bold"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["badge_bg_color"] == "#112233"
    assert body["badge_weight"] == "bold"
    # 他のフィールドは既定値のまま保たれること
    assert body["body_weight"] == "medium"
    assert state["config"]["text_style"]["badge_bg_color"] == "#112233"


def test_update_text_style_rejects_invalid_color(client):
    fake_client, _ = client
    resp = fake_client.put("/api/index?resource=text_style", json={"badge_bg_color": "not-a-color"})
    assert resp.status_code == 400


def test_update_text_style_rejects_invalid_weight(client):
    fake_client, _ = client
    resp = fake_client.put("/api/index?resource=text_style", json={"badge_weight": "ultra-mega-bold"})
    assert resp.status_code == 400


def test_text_style_requires_login(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)
    anonymous_client = index.app.test_client()
    resp = anonymous_client.put("/api/index?resource=text_style", json={"badge_weight": "bold"})
    assert resp.status_code == 401
