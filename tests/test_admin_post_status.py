import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin" / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))

import index  # noqa: E402
from github_client import GithubClientError  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)

    # post_history.json の読み込みは既定では空にしておく（個々のテストで上書きする）
    monkeypatch.setattr(index.github_client, "get_json", lambda path, default: default)

    fake_client = index.app.test_client()
    with fake_client.session_transaction() as sess:
        sess["email"] = "staff@example.com"
        sess["role"] = "user"

    return fake_client


def _run(status="completed", conclusion="success", created_at="2026-08-04T22:00:00Z", run_id=1):
    return {
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "html_url": f"https://github.com/x/y/actions/runs/{run_id}",
    }


def test_post_status_reports_no_history(client, monkeypatch):
    monkeypatch.setattr(index.github_client, "list_scheduled_runs", lambda workflow_file, limit=10: [])
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["state"] == "no_history"
    assert body["history"] == []


def test_post_status_reports_success_and_includes_history(client, monkeypatch):
    runs = [
        _run(conclusion="success", created_at="2026-08-04T22:00:00Z", run_id=2),
        _run(conclusion="failure", created_at="2026-08-03T22:00:00Z", run_id=1),
    ]
    monkeypatch.setattr(index.github_client, "list_scheduled_runs", lambda workflow_file, limit=10: runs)
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["state"] == "success"
    assert body["created_at"] == "2026-08-04T22:00:00Z"
    assert len(body["history"]) == 2
    assert [h["state"] for h in body["history"]] == ["success", "failure"]


def test_post_status_reports_failure(client, monkeypatch):
    monkeypatch.setattr(
        index.github_client, "list_scheduled_runs", lambda workflow_file, limit=10: [_run(conclusion="failure")]
    )
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    assert resp.get_json()["state"] == "failure"


def test_post_status_reports_running_when_not_completed(client, monkeypatch):
    monkeypatch.setattr(
        index.github_client,
        "list_scheduled_runs",
        lambda workflow_file, limit=10: [_run(status="in_progress", conclusion=None)],
    )
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    assert resp.get_json()["state"] == "running"


def test_post_status_surfaces_github_client_error(client, monkeypatch):
    def _raise(workflow_file, limit=10):
        raise GithubClientError("実行履歴の取得に失敗しました")

    monkeypatch.setattr(index.github_client, "list_scheduled_runs", _raise)
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 502


def test_post_status_includes_latest_x_post_url_when_available(client, monkeypatch):
    monkeypatch.setattr(
        index.github_client, "list_scheduled_runs", lambda workflow_file, limit=10: [_run(conclusion="success")]
    )
    history_data = {
        "history": [
            {"date": "2026-08-03", "platforms_posted": ["x"], "post_ids": {"x": "111"}},
            {"date": "2026-08-04", "platforms_posted": ["x"], "post_ids": {"x": "222"}},
        ]
    }
    monkeypatch.setattr(
        index.github_client,
        "get_json",
        lambda path, default: history_data if path == index.POST_HISTORY_PATH else default,
    )
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    assert resp.get_json()["latest_x_post_url"] == "https://x.com/i/web/status/222"


def test_post_status_latest_x_post_url_is_none_when_no_x_posts_recorded(client, monkeypatch):
    monkeypatch.setattr(
        index.github_client, "list_scheduled_runs", lambda workflow_file, limit=10: [_run(conclusion="success")]
    )
    history_data = {"history": [{"date": "2026-08-04", "platforms_posted": ["instagram"], "post_ids": {}}]}
    monkeypatch.setattr(
        index.github_client,
        "get_json",
        lambda path, default: history_data if path == index.POST_HISTORY_PATH else default,
    )
    resp = client.get("/api/index?resource=post_status")
    assert resp.status_code == 200
    assert resp.get_json()["latest_x_post_url"] is None


def test_post_status_requires_login(monkeypatch):
    index.app.secret_key = "test-secret-key"
    index.app.config.update(SESSION_COOKIE_SECURE=False, TESTING=True)
    anonymous_client = index.app.test_client()
    resp = anonymous_client.get("/api/index?resource=post_status")
    assert resp.status_code == 401
