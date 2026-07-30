"""Instagram Graph API（Facebookページ経由）へのストーリー投稿。

開発仕様書の検証結果どおり、Instagram専用ログイン（graph.instagram.com への直接POST）は
このアプリ構成では "Invalid platform app" エラーになるため使用しない。
必ず graph.facebook.com 経由（Facebookページに連携したInstagramビジネスアカウント）で操作する。

media_type=STORIES を指定した2段階の投稿フロー:
  1. POST /{ig-user-id}/media        (image_url, media_type=STORIES) -> creation_id
  2. POST /{ig-user-id}/media_publish (creation_id)                  -> 公開

キーワードを含む文章はPillowで画像に焼き込み済み（caption_overlay.py）のため、
Instagramのcaptionフィールド（ストーリーでは表示されない）へは送らない。

Meta App Reviewが未承認のため、既定では dry_run=True（本モジュールは呼ばれるが実行はされない）。
承認後に ENABLE_INSTAGRAM=true にすると有効化される。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from .. import config
from .base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com"


class InstagramPublisher(BasePublisher):
    platform = "instagram"

    def __init__(self, dry_run: bool = True, session: Optional[requests.Session] = None):
        super().__init__(dry_run=dry_run)
        self._session = session or requests

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
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")
        if not creation_id:
            raise RuntimeError(f"creation_idの取得に失敗しました: {create_resp.text}")

        publish_resp = self._session.post(
            f"{base_url}/{config.IG_USER_ID}/media_publish",
            data={"creation_id": creation_id, "access_token": config.META_ACCESS_TOKEN},
            timeout=30,
        )
        publish_resp.raise_for_status()
        media_id = publish_resp.json().get("id")

        logger.info("Instagramストーリーへ投稿しました: media_id=%s", media_id)
        return PublishResult(
            platform=self.platform,
            success=True,
            detail="投稿しました。",
            post_id=media_id,
        )
