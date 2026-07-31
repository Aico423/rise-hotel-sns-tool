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

    state = {
        "config": {
            "room_types": [
                {"name": "Type A", "bed_size": "King 180cm×200cm", "max_guests": 10},
                {"name": "Type B", "bed_size": "Queen 180cm×200cm", "max_guests": 8},
            ]
        },
        "materials": {
            "materials": [
                {"id": "mat-1", "room_type": "Type A", "room_number": "601", "updated_at": "old"},
            ]
        },
    }

    def fake_get_json(path, default):
        if path == index.CONFIG_PATH:
            return state["config"]
        if path == index.MATERIALS_PATH:
            return state["materials"]
        return default

    def fake_update_json_with_retry(path, mutate_fn, message, default, retries=2):
        if path == index.CONFIG_PATH:
            state["config"] = mutate_fn(state["config"])
            return state["config"]
        if path == index.MATERIALS_PATH:
            state["materials"] = mutate_fn(state["materials"])
            return state["materials"]
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(index.github_client, "get_json", fake_get_json)
    monkeypatch.setattr(index.github_client, "update_json_with_retry", fake_update_json_with_retry)

    fake_client = index.app.test_client()
    with fake_client.session_transaction() as sess:
        sess["email"] = "staff@example.com"
        sess["role"] = "user"

    return fake_client, state


def test_list_room_types(client):
    fake_client, _ = client
    resp = fake_client.get("/api/index?resource=room_types")
    assert resp.status_code == 200
    names = [rt["name"] for rt in resp.get_json()["room_types"]]
    assert names == ["Type A", "Type B"]


def test_create_room_type(client):
    fake_client, state = client
    resp = fake_client.post(
        "/api/index?resource=room_types",
        json={"name": "Type C", "bed_size": "Double 140cm×200cm", "max_guests": "Up to 3 pax"},
    )
    assert resp.status_code == 201
    assert resp.get_json() == {"name": "Type C", "bed_size": "Double 140cm×200cm", "max_guests": "Up to 3 pax"}
    assert [rt["name"] for rt in state["config"]["room_types"]] == ["Type A", "Type B", "Type C"]


def test_create_room_type_requires_name(client):
    fake_client, _ = client
    resp = fake_client.post("/api/index?resource=room_types", json={"bed_size": "King"})
    assert resp.status_code == 400


def test_create_room_type_rejects_duplicate_name(client):
    fake_client, _ = client
    resp = fake_client.post("/api/index?resource=room_types", json={"name": "Type A"})
    assert resp.status_code == 400


def test_update_room_type_fields(client):
    fake_client, state = client
    resp = fake_client.put(
        "/api/index?resource=room_types&id=Type A",
        json={"bed_size": "King 180cm×200cm", "max_guests": "Up to 10 pax"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["max_guests"] == "Up to 10 pax"
    assert state["config"]["room_types"][0]["max_guests"] == "Up to 10 pax"
    # 部屋番号を変更していないので、素材側の room_type はそのまま
    assert state["materials"]["materials"][0]["room_type"] == "Type A"


def test_update_room_type_rename_cascades_to_materials(client):
    fake_client, state = client
    resp = fake_client.put("/api/index?resource=room_types&id=Type A", json={"name": "Deluxe Type A"})
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Deluxe Type A"
    assert state["config"]["room_types"][0]["name"] == "Deluxe Type A"
    assert state["materials"]["materials"][0]["room_type"] == "Deluxe Type A"
    assert state["materials"]["materials"][0]["updated_at"] != "old"


def test_update_room_type_rename_rejects_duplicate(client):
    fake_client, _ = client
    resp = fake_client.put("/api/index?resource=room_types&id=Type A", json={"name": "Type B"})
    assert resp.status_code == 400


def test_update_room_type_not_found(client):
    fake_client, _ = client
    resp = fake_client.put("/api/index?resource=room_types&id=Does Not Exist", json={"bed_size": "King"})
    assert resp.status_code == 404


def test_delete_room_type_blocked_when_in_use(client):
    fake_client, state = client
    resp = fake_client.delete("/api/index?resource=room_types&id=Type A")
    assert resp.status_code == 400
    assert [rt["name"] for rt in state["config"]["room_types"]] == ["Type A", "Type B"]


def test_delete_room_type_succeeds_when_unused(client):
    fake_client, state = client
    resp = fake_client.delete("/api/index?resource=room_types&id=Type B")
    assert resp.status_code == 200
    assert [rt["name"] for rt in resp.get_json()["room_types"]] == ["Type A"]


def test_room_types_requires_login(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)
    anonymous_client = index.app.test_client()
    resp = anonymous_client.get("/api/index?resource=room_types")
    assert resp.status_code == 401
