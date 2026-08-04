import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin" / "api"))

import index  # noqa: E402
import user_store  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)

    users: dict[str, dict] = {}

    def fake_any_users_exist():
        return bool(users)

    def fake_create_user(email, password, role):
        email = email.strip().lower()
        if not email or "@" not in email:
            raise user_store.UserStoreError("メールアドレスの形式が正しくありません。")
        if len(password) < 8:
            raise user_store.UserStoreError("パスワードは8文字以上にしてください。")
        if email in users:
            raise user_store.UserStoreError("そのメールアドレスはすでに登録されています。")
        users[email] = {"email": email, "role": role, "password": password}
        return {"email": email, "role": role, "created_at": "2026-07-30T00:00:00+00:00"}

    def fake_verify_password(email, password):
        user = users.get(email.strip().lower())
        if not user or user["password"] != password:
            return None
        return {"email": user["email"], "role": user["role"]}

    def fake_list_users():
        return [{"email": u["email"], "role": u["role"], "created_at": "2026-07-30T00:00:00+00:00"} for u in users.values()]

    def fake_delete_user(email):
        email = email.strip().lower()
        if email not in users:
            raise user_store.UserStoreError("対象のユーザーが見つかりませんでした。")
        if users[email]["role"] == "admin":
            remaining_admins = [u for u in users.values() if u["role"] == "admin" and u["email"] != email]
            if not remaining_admins:
                raise user_store.UserStoreError("最後の管理者アカウントは削除できません。")
        del users[email]

    def fake_get_user(email):
        user = users.get(email.strip().lower())
        if not user:
            return None
        return {"email": user["email"], "role": user["role"], "password_hash": "x", "created_at": "2026-07-30T00:00:00+00:00"}

    def fake_update_user(email, role=None, new_password=None):
        email = email.strip().lower()
        if email not in users:
            raise user_store.UserStoreError("対象のユーザーが見つかりませんでした。")
        if role is not None:
            if role not in ("admin", "user"):
                raise user_store.UserStoreError("権限の指定が正しくありません。")
            if users[email]["role"] == "admin" and role != "admin":
                remaining_admins = [u for u in users.values() if u["role"] == "admin" and u["email"] != email]
                if not remaining_admins:
                    raise user_store.UserStoreError("最後の管理者アカウントの権限は変更できません。")
            users[email]["role"] = role
        if new_password is not None:
            if len(new_password) < 8:
                raise user_store.UserStoreError("パスワードは8文字以上にしてください。")
            users[email]["password"] = new_password
        return {"email": email, "role": users[email]["role"], "created_at": "2026-07-30T00:00:00+00:00"}

    monkeypatch.setattr(index.user_store, "any_users_exist", fake_any_users_exist)
    monkeypatch.setattr(index.user_store, "create_user", fake_create_user)
    monkeypatch.setattr(index.user_store, "verify_password", fake_verify_password)
    monkeypatch.setattr(index.user_store, "list_users", fake_list_users)
    monkeypatch.setattr(index.user_store, "delete_user", fake_delete_user)
    monkeypatch.setattr(index.user_store, "get_user", fake_get_user)
    monkeypatch.setattr(index.user_store, "update_user", fake_update_user)

    return index.app.test_client()


def test_bootstrap_needed_when_no_users(client):
    resp = client.get("/api/index?resource=bootstrap")
    assert resp.status_code == 200
    assert resp.get_json()["needs_setup"] is True


def test_materials_requires_login(client):
    resp = client.get("/api/index?resource=materials")
    assert resp.status_code == 401


def test_bootstrap_creates_first_admin_and_logs_in(client):
    resp = client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    assert resp.status_code == 201
    assert resp.get_json()["role"] == "admin"

    session_resp = client.get("/api/index?resource=session")
    body = session_resp.get_json()
    assert body["logged_in"] is True
    assert body["role"] == "admin"


def test_bootstrap_refuses_when_user_already_exists(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    resp = client.post("/api/index?resource=bootstrap", json={"email": "second@example.com", "password": "password123"})
    assert resp.status_code == 403


def test_login_success_and_failure(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    client.post("/api/index?resource=logout")

    bad = client.post("/api/index?resource=login", json={"email": "admin@example.com", "password": "wrong"})
    assert bad.status_code == 401

    good = client.post("/api/index?resource=login", json={"email": "admin@example.com", "password": "password123"})
    assert good.status_code == 200
    assert good.get_json()["role"] == "admin"


def test_logout_clears_session(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    client.post("/api/index?resource=logout")
    resp = client.get("/api/index?resource=session")
    assert resp.get_json()["logged_in"] is False


def test_non_admin_cannot_manage_users(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    client.post("/api/index?resource=users", json={"email": "staff@example.com", "password": "password123", "role": "user"})
    client.post("/api/index?resource=logout")
    client.post("/api/index?resource=login", json={"email": "staff@example.com", "password": "password123"})

    resp = client.get("/api/index?resource=users")
    assert resp.status_code == 403


def test_admin_can_create_and_list_users(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    create_resp = client.post(
        "/api/index?resource=users", json={"email": "staff@example.com", "password": "password123", "role": "user"}
    )
    assert create_resp.status_code == 201

    list_resp = client.get("/api/index?resource=users")
    emails = {u["email"] for u in list_resp.get_json()["users"]}
    assert emails == {"admin@example.com", "staff@example.com"}


def test_admin_cannot_delete_own_account(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    resp = client.delete("/api/index?resource=users&id=admin@example.com")
    assert resp.status_code == 400


def test_admin_can_delete_other_user(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    client.post("/api/index?resource=users", json={"email": "staff@example.com", "password": "password123", "role": "user"})

    resp = client.delete("/api/index?resource=users&id=staff@example.com")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.get_json()["users"]}
    assert emails == {"admin@example.com"}


def test_admin_can_update_other_users_role(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    client.post("/api/index?resource=users", json={"email": "staff@example.com", "password": "password123", "role": "user"})

    resp = client.put("/api/index?resource=users&id=staff@example.com", json={"role": "admin"})
    assert resp.status_code == 200
    assert resp.get_json()["role"] == "admin"


def test_admin_can_reset_another_users_password(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    client.post("/api/index?resource=users", json={"email": "staff@example.com", "password": "old-password", "role": "user"})

    resp = client.put("/api/index?resource=users&id=staff@example.com", json={"password": "new-password123"})
    assert resp.status_code == 200

    client.post("/api/index?resource=logout")
    login_resp = client.post("/api/index?resource=login", json={"email": "staff@example.com", "password": "new-password123"})
    assert login_resp.status_code == 200


def test_update_user_returns_404_for_unknown_email(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    resp = client.put("/api/index?resource=users&id=nobody@example.com", json={"role": "admin"})
    assert resp.status_code == 404


def test_update_user_refuses_to_demote_last_admin(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    resp = client.put("/api/index?resource=users&id=admin@example.com", json={"role": "user"})
    assert resp.status_code == 400


def test_non_admin_cannot_update_users(client):
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    client.post("/api/index?resource=users", json={"email": "staff@example.com", "password": "password123", "role": "user"})
    client.post("/api/index?resource=logout")
    client.post("/api/index?resource=login", json={"email": "staff@example.com", "password": "password123"})

    resp = client.put("/api/index?resource=users&id=staff@example.com", json={"role": "admin"})
    assert resp.status_code == 403


def test_config_accessible_once_logged_in(client, monkeypatch):
    monkeypatch.setattr(index.github_client, "get_json", lambda path, default: default)
    client.post("/api/index?resource=bootstrap", json={"email": "admin@example.com", "password": "password123"})
    resp = client.get("/api/index?resource=config")
    assert resp.status_code == 200
