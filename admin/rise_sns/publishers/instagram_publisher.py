"""Instagram Graph API（Facebookページ経由）へのストーリー投稿。

開発仕様書の検証結果どおり、Instagram専用ログイン（graph.instagram.com への直接POST）は
このアプリ構成では "Invalid platform app" エラーになるため使用しない。
必ず graph.facebook.com 経由（Facebookページに連携したInstagramビジネスアカウント）で操作する。

media_type=STORIES を指定した3段階の投稿フロー:
  1. POST /{ig-user-id}/media        (image_url, media_type=STORIES) -> creation_id
  2. GET  /{creation_id}?fields=status_code                          -> FINISHEDになるまで待機
  3. POST /{ig-user-id}/media_publish (creation_id)                  -> 公開

手順2が無いと、画像URLの取り込み処理が完了する前にmedia_publishを呼んでしまい、
「Media ID is not available」(code 9007) で失敗することがある（image_urlの画像取得は非同期のため）。

キーワードを含む文章はPillowで画像に焼き込み済み（caption_overlay.py）のため、
Instagramのcaptionフィールド（ストーリーでは表示されない）へは送らない。

Meta App Reviewが未承認のため、既定では dry_run=True（本モジュールは呼ばれるが実行はされない）。
承認後に ENABLE_INSTAGRAM=true にすると有効化される。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import requests

from .. import config
from .base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com"
MEDIA_CONTAINER_MAX_ATTEMPTS = 10
MEDIA_CONTAINER_POLL_INTERVAL_SECONDS = 2


class InstagramPublisher(BasePublisher):
    platform = "instagram"

    def __init__(
        self,
        dry_run: bool = True,
        session: Optional[requests.Session] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        super().__init__(dry_run=dry_run)
        self._session = session or requests
        self._sleep_fn = sleep_fn

    def _wait_until_container_ready(self, creation_id: str, base_url: str) -> None:
        for _ in range(MEDIA_CONTAINER_MAX_ATTEMPTS):
            status_resp = self._session.get(
                f"{base_url}/{creation_id}",
                params={"fields": "status_code", "access_token": config.META_ACCESS_TOKEN},
                timeout=30,
            )
            if status_resp.status_code >= 400:
                raise RuntimeError(f"画像の準備状況の確認に失敗しました（応答: {status_resp.text}）。")
            status_code = status_resp.json().get("status_code")
            if status_code == "FINISHED":
                return
            if status_code == "ERROR":
                raise RuntimeError(f"画像の準備に失敗しました（応答: {status_resp.text}）。")
            self._sleep_fn(MEDIA_CONTAINER_POLL_INTERVAL_SECONDS)
        raise RuntimeError("画像の準備が時間内に完了しませんでした。もう一度お試しください。")

    def _publish(
        self,
        caption: str,
        image_path: Optional[Path] = None,
        image_url: Optional[str] = None,
    ) -> PublishResult:
        if image_url is None:
            raise ValueError("Instagram投稿には公開URL（image_url）が必要です。")
        if not config.META_ACCESS_TOKEN or not config.IG_USER_ID:
            raise RuntimeError("META_ACCESS_TOKEN または IG_USER_ID が設定されていません。")

        base_url = f"{GRAPH_API_BASE}/{config.META_GRAPH_API_VERSION}"

        create_resp = self._session.post(
            f"{base_url}/{config.IG_USER_ID}/media",
            data={
                "image_url": image_url,
                "media_type": "STORIES",
                "access_token": config.META_ACCESS_TOKEN,
            },
            timeout=30,
        )
        if create_resp.status_code >= 400:
            raise RuntimeError(f"画像の準備に失敗しました（応答: {create_resp.text}）。")
        creation_id = create_resp.json().get("id")
        if not creation_id:
            raise RuntimeError(f"creation_idの取得に失敗しました: {create_resp.text}")

        self._wait_until_container_ready(creation_id, base_url)

        publish_resp = self._session.post(
            f"{base_url}/{config.IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": config.META_ACCESS_TOKEN},
            timeout=30,
        )
        if publish_resp.status_code >= 400:
            raise RuntimeError(f"公開に失敗しました（応答: {publish_resp.text}）。")
        media_id = publish_resp.json().get("id")
        if not media_id:
            # APIがエラーを返さなくても投稿IDが無ければ実際には公開できていない可能性が高いため、
            # 黙って成功扱いにしない（Xの投稿で見つかった不具合と同じ種類の抜け穴を防ぐ）。
            raise RuntimeError(f"投稿IDを取得できませんでした（応答: {publish_resp.text}）。")

        logger.info("Instagramストーリーへ投稿しました: media_id=%s", media_id)
        return PublishResult(
            platform=self.platform,
            success=True,
            detail="投稿しました。",
            post_id=media_id,
        )
