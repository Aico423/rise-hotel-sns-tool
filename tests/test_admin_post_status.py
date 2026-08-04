import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))

import index  # noqa: E402
from github_client import GithubClientError  # noqa: E402


@pytest.fixture
def client():
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)

    fake_client = index.app.test_client()
    with fake_client.session_transaction() as sess:
        sess["email"] = "staff@example.com"
        sess["role"] = "user"

    return fake_client


def test_post_status_reports_no_history(client, monkeypatch):
    monkeypatch.setattr(index.github_client, "get_latest_scheduled_run", lambda workflow_file: None)
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    assert resp.get_json()["state"] == "no_history"


def test_post_status_reports_success(client, monkeypatch):
    monkeypatch.setattr(
        index.github_client,
        "get_latest_scheduled_run",
        lambda workflow_file: {
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-08-04T22:00:00Z",
            "html_url": "https://github.com/x/y/actions/runs/1",
        },
    )
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["state"] == "success"
    assert body["created_at"] == "2026-08-04T22:00:00Z"


def test_post_status_reports_failure(client, monkeypatch):
    monkeypatch.setattr(
        index.github_client,
        "get_latest_scheduled_run",
        lambda workflow_file: {
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2026-08-04T22:00:00Z",
            "html_url": "https://github.com/x/y/actions/runs/2",
        },
    )
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    assert resp.get_json()["state"] == "failure"


def test_post_status_reports_running_when_not_completed(client, monkeypatch):
    monkeypatch.setattr(
        index.github_client,
        "get_latest_scheduled_run",
        lambda workflow_file: {
            "status": "in_progress",
            "conclusion": None,
            "created_at": "2026-08-04T22:00:00Z",
            "html_url": "https://github.com/x/y/actions/runs/3",
        },
    )
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    assert resp.get_json()["state"] == "running"


def test_post_status_surfaces_github_client_error(client, monkeypatch):
    def _raise(workflow_file):
        raise GithubClientError("実行履歴の取得に失敗しました")

    monkeypatch.setattr(index.github_client, "get_latest_scheduled_run", _raise)
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 502


def test_post_status_requires_login(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)
    anonymous_client = index.app.test_client()
    resp = anonymous_client.get("/api/index?resource=post_status")
    assert resp.status_code == 401
