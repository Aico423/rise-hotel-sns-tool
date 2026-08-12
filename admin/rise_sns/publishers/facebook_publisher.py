"""FacebookページへのStories投稿（story-firstだが、feed投稿へのフォールバック付き）。

【重要】Facebookページの写真ストーリー公開APIは、通常のフィード投稿ほど仕様が安定しておらず、
本実装時点では正式なエンドポイント名が未確定。config.FACEBOOK_STORY_ENDPOINT
（既定値 "photo_stories"）は変更されうる前提の設定値であり、有効化前に必ず最新の
Graph APIドキュメントを確認すること。

FACEBOOK_POST_MODE="story" : 非公開写真をアップロード後、ストーリー用エンドポイントにアタッチを試みる
FACEBOOK_POST_MODE="feed"  : 通常のページ投稿（/{page-id}/photos に公開状態でPOST）※既定値
確認が取れるまでは既定を "feed" にしておき、通常のフィード投稿と誤ってストーリー実装を
混同しないよう、両モードを明確に分離してある。

Meta App Reviewが未承認のため、既定では dry_run=True。承認後に ENABLE_FACEBOOK=true にすると有効化される。
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


class FacebookPublisher(BasePublisher):
    platform = "facebook"

    def __init__(self, dry_run: bool = True, session: Optional[requests.Session] = None, post_mode: Optional[str] = None):
        super().__init__(dry_run=dry_run)
        self._session = session or requests
        self.post_mode = post_mode or config.FACEBOOK_POST_MODE

    def _publish(
        self,
        caption: str,
        image_path: Optional[Path] = None,
        image_url: Optional[str] = None,
    ) -> PublishResult:
        if image_url is None:
            raise ValueError("Facebook投稿には公開URL（image_url）が必要です。")
        if not config.META_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
            raise RuntimeError("META_ACCESS_TOKEN または FACEBOOK_PAGE_ID が設定されていません。")

        if self.post_mode == "story":
            return self._publish_story(image_url)
        return self._publish_feed(caption, image_url)

    def _publish_feed(self, caption: str, image_url: str) -> PublishResult:
        base_url = f"{GRAPH_API_BASE}/{config.META_GRAPH_API_VERSION}"
        resp = self._session.post(
            f"{base_url}/{config.FACEBOOK_PAGE_ID}/photos",
            data={
                "url": image_url,
                "caption": caption,
                "access_token": config.META_ACCESS_TOKEN,
            },
            timeout=30,
        )
        resp.raise_for_status()
        post_id = resp.json().get("post_id") or resp.json().get("id")
        if not post_id:
            raise RuntimeError(f"投稿IDを取得できませんでした（応答: {resp.text}）。")
        logger.info("Facebookページへ投稿しました（フィード）: post_id=%s", post_id)
        return PublishResult(platform=self.platform, success=True, detail="投稿しました（通常投稿）。", post_id=post_id)

    def _publish_story(self, image_url: str) -> PublishResult:
        base_url = f"{GRAPH_API_BASE}/{config.META_GRAPH_API_VERSION}"

        # 1) 非公開写真としてアップロード
        upload_resp = self._session.post(
            f"{base_url}/{config.FACEBOOK_PAGE_ID}/photos",
            data={
                "url": image_url,
                "published": "false",
                "access_token": config.META_ACCESS_TOKEN,
            },
            timeout=30,
        )
        upload_resp.raise_for_status()
        photo_id = upload_resp.json().get("id")
        if not photo_id:
            raise RuntimeError(f"写真のアップロードに失敗しました: {upload_resp.text}")

        # 2) ストーリー用エンドポイントにアタッチ（要検証：エンドポイント名は変更されうる）
        story_resp = self._session.post(
            f"{base_url}/{config.FACEBOOK_PAGE_ID}/{config.FACEBOOK_STORY_ENDPOINT}",
            data={"photo_id": photo_id, "access_token": config.META_ACCESS_TOKEN},
            timeout=30,
        )
        story_resp.raise_for_status()
        story_id = story_resp.json().get("id") or story_resp.json().get("post_id")
        if not story_id:
            raise RuntimeError(f"投稿IDを取得できませんでした（応答: {story_resp.text}）。")

        logger.info("Facebookページへ投稿しました（ストーリー）: id=%s", story_id)
        return PublishResult(platform=self.platform, success=True, detail="投稿しました（ストーリー）。", post_id=story_id)
