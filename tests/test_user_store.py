import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin" / "api"))

import user_store  # noqa: E402


class FakeRedis:
    """user_store._command が期待する最小限のRedisコマンドをインメモリで再現する。"""

    def __init__(self):
        self.hashes: dict[str, dict[str, str]] = {}
        self.sets: dict[str, set[str]] = {}

    def command(self, *parts):
        cmd = parts[0].upper()
        if cmd == "HSET":
            key = parts[1]
            fields = parts[2:]
            store = self.hashes.setdefault(key, {})
            for field, value in zip(fields[0::2], fields[1::2]):
                store[field] = value
            return len(fields) // 2
        if cmd == "HGETALL":
            key = parts[1]
            store = self.hashes.get(key, {})
            flat = []
            for k, v in store.items():
                flat.extend([k, v])
            return flat
        if cmd == "SADD":
            key, member = parts[1], parts[2]
            self.sets.setdefault(key, set()).add(member)
            return 1
        if cmd == "SREM":
            key, member = parts[1], parts[2]
            self.sets.get(key, set()).discard(member)
            return 1
        if cmd == "SMEMBERS":
            key = parts[1]
            return list(self.sets.get(key, set()))
        if cmd == "DEL":
            key = parts[1]
            self.hashes.pop(key, None)
            return 1
        raise AssertionError(f"unexpected command in test: {parts}")


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(user_store, "_command", fake.command)
    return fake


def test_any_users_exist_false_initially(fake_redis):
    assert user_store.any_users_exist() is False


def test_create_user_then_exists(fake_redis):
    user_store.create_user("Admin@Example.com", "password123", "admin")
    assert user_store.any_users_exist() is True
    user = user_store.get_user("admin@example.com")
    assert user["role"] == "admin"
    assert user["password_hash"] != "password123"


def test_create_user_rejects_short_password(fake_redis):
    with pytest.raises(user_store.UserStoreError):
        user_store.create_user("a@example.com", "short", "admin")


def test_create_user_rejects_invalid_email(fake_redis):
    with pytest.raises(user_store.UserStoreError):
        user_store.create_user("not-an-email", "password123", "admin")


def test_create_user_rejects_invalid_role(fake_redis):
    with pytest.raises(user_store.UserStoreError):
        user_store.create_user("a@example.com", "password123", "superadmin")


def test_create_user_rejects_duplicate_email(fake_redis):
    user_store.create_user("a@example.com", "password123", "user")
    with pytest.raises(user_store.UserStoreError):
        user_store.create_user("a@example.com", "password456", "admin")


def test_verify_password_success(fake_redis):
    user_store.create_user("a@example.com", "correct-password", "user")
    result = user_store.verify_password("a@example.com", "correct-password")
    assert result == {"email": "a@example.com", "role": "user"}


def test_verify_password_wrong_password(fake_redis):
    user_store.create_user("a@example.com", "correct-password", "user")
    assert user_store.verify_password("a@example.com", "wrong-password") is None


def test_verify_password_unknown_email(fake_redis):
    assert user_store.verify_password("nobody@example.com", "whatever1") is None


def test_list_users_excludes_password_hash(fake_redis):
    user_store.create_user("a@example.com", "password123", "admin")
    users = user_store.list_users()
    assert len(users) == 1
    assert "password_hash" not in users[0]
    assert users[0]["email"] == "a@example.com"


def test_delete_user_removes_account(fake_redis):
    user_store.create_user("a@example.com", "password123", "admin")
    user_store.create_user("b@example.com", "password123", "user")
    user_store.delete_user("b@example.com")
    assert user_store.get_user("b@example.com") is None
    assert len(user_store.list_users()) == 1


def test_delete_user_refuses_to_remove_last_admin(fake_redis):
    user_store.create_user("only-admin@example.com", "password123", "admin")
    with pytest.raises(user_store.UserStoreError):
        user_store.delete_user("only-admin@example.com")


def test_delete_user_allows_removing_admin_when_another_admin_remains(fake_redis):
    user_store.create_user("admin1@example.com", "password123", "admin")
    user_store.create_user("admin2@example.com", "password123", "admin")
    user_store.delete_user("admin1@example.com")
    remaining = user_store.list_users()
    assert [u["email"] for u in remaining] == ["admin2@example.com"]


def test_delete_user_raises_for_unknown_email(fake_redis):
    with pytest.raises(user_store.UserStoreError):
        user_store.delete_user("nobody@example.com")
