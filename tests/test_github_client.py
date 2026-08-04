import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin" / "api"))

import github_client  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "Aico423/rise-hotel-sns-tool")
    monkeypatch.setenv("GITHUB_PAT", "fake-token")


def test_get_latest_scheduled_run_returns_none_when_no_runs(env, monkeypatch):
    monkeypatch.setattr(
        github_client.requests, "get", lambda *a, **k: _FakeResponse(200, {"workflow_runs": []})
    )
    assert github_client.get_latest_scheduled_run("daily-post.yml") is None


def test_get_latest_scheduled_run_returns_latest_run_details(env, monkeypatch):
    run = {
        "status": "completed",
        "conclusion": "success",
        "created_at": "2026-08-04T22:00:00Z",
        "html_url": "https://github.com/Aico423/rise-hotel-sns-tool/actions/runs/123",
    }

    def fake_get(url, headers, params, timeout):
        assert params["event"] == "schedule"
        return _FakeResponse(200, {"workflow_runs": [run]})

    monkeypatch.setattr(github_client.requests, "get", fake_get)
    result = github_client.get_latest_scheduled_run("daily-post.yml")
    assert result == run


def test_get_latest_scheduled_run_raises_on_http_error(env, monkeypatch):
    monkeypatch.setattr(
        github_client.requests, "get", lambda *a, **k: _FakeResponse(500, {}, text="server error")
    )
    with pytest.raises(github_client.GithubClientError):
        github_client.get_latest_scheduled_run("daily-post.yml")
