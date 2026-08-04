"""GitHub Contents API への薄いラッパー。

管理画面（Vercelの関数）は、このリポジトリのデータファイル（data/*.json, data/images/*）を
GitHub PAT（このリポジトリ専用・Contents読み書き権限のみ）を使って直接読み書きする。
PATはサーバー側の環境変数からのみ読み込み、ブラウザ側には一切渡さない。
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Callable, Optional

import requests

API_BASE = "https://api.github.com"


class GithubClientError(RuntimeError):
    """スタッフ向けには「保存に失敗しました」等の平易なメッセージに変換して見せる想定のエラー。"""


def _repo() -> str:
    repo = os.environ.get("GITHUB_REPO", "")
    if not repo:
        raise GithubClientError("GITHUB_REPO が設定されていません。")
    return repo


def _branch() -> str:
    return os.environ.get("GITHUB_BRANCH", "main")


def _headers() -> dict:
    token = os.environ.get("GITHUB_PAT", "")
    if not token:
        raise GithubClientError("GITHUB_PAT が設定されていません。")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def get_file(path: str) -> tuple[Optional[bytes], Optional[str]]:
    """(内容のbytes, sha) を返す。存在しない場合は (None, None)。"""
    url = f"{API_BASE}/repos/{_repo()}/contents/{path}"
    resp = requests.get(url, headers=_headers(), params={"ref": _branch()}, timeout=20)
    if resp.status_code == 404:
        return None, None
    if resp.status_code >= 400:
        raise GithubClientError(f"GitHubからの読み込みに失敗しました: {resp.status_code} {resp.text}")
    data = resp.json()
    content = base64.b64decode(data["content"])
    return content, data["sha"]


def get_json(path: str, default: Any) -> Any:
    content, _ = get_file(path)
    if content is None:
        return default
    return json.loads(content.decode("utf-8"))


def put_file(path: str, content_bytes: bytes, message: str, sha: Optional[str] = None) -> dict:
    url = f"{API_BASE}/repos/{_repo()}/contents/{path}"
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": _branch(),
    }
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=_headers(), json=payload, timeout=30)
    if resp.status_code >= 400:
        raise GithubClientError(f"GitHubへの保存に失敗しました: {resp.status_code} {resp.text}")
    return resp.json()


def delete_file(path: str, message: str) -> None:
    _, sha = get_file(path)
    if sha is None:
        return
    url = f"{API_BASE}/repos/{_repo()}/contents/{path}"
    resp = requests.delete(
        url,
        headers=_headers(),
        json={"message": message, "sha": sha, "branch": _branch()},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise GithubClientError(f"GitHubからの削除に失敗しました: {resp.status_code} {resp.text}")


def update_json_with_retry(
    path: str,
    mutate_fn: Callable[[Any], Any],
    message: str,
    default: Any,
    retries: int = 2,
) -> Any:
    """読み込み→更新→書き込みを行う。sha競合時は再取得して再試行する（楽観的排他制御）。"""
    last_error: Optional[Exception] = None
    for _ in range(retries + 1):
        content, sha = get_file(path)
        data = json.loads(content.decode("utf-8")) if content is not None else default
        new_data = mutate_fn(data)
        content_bytes = (json.dumps(new_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        try:
            put_file(path, content_bytes, message, sha=sha)
            return new_data
        except GithubClientError as exc:
            last_error = exc
            continue
    raise GithubClientError("保存に失敗しました。もう一度お試しください。") from last_error


def public_raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{_repo()}/{_branch()}/{path}"


def list_scheduled_runs(workflow_file: str, limit: int = 10) -> list[dict]:
    """毎日の自動実行（スケジュール起動）の直近の実行履歴を、新しい順に返す。

    スタッフが手動で試しに実行したもの（workflow_dispatch）は対象外にし、
    「毎朝の自動投稿がちゃんと動いているか」だけを見せられるようにする。
    """
    url = f"{API_BASE}/repos/{_repo()}/actions/workflows/{workflow_file}/runs"
    resp = requests.get(
        url,
        headers=_headers(),
        params={"event": "schedule", "per_page": limit},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise GithubClientError(f"実行履歴の取得に失敗しました: {resp.status_code} {resp.text}")
    runs = resp.json().get("workflow_runs", [])
    return [
        {
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"),
            "html_url": run.get("html_url"),
        }
        for run in runs
    ]


def get_latest_scheduled_run(workflow_file: str) -> Optional[dict]:
    """直近1件だけを返す（見つからない場合はNone）。"""
    runs = list_scheduled_runs(workflow_file, limit=1)
    return runs[0] if runs else None
