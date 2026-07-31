"""X（旧Twitter）への投稿。

認証はOAuth1.0a（APIキー/シークレット + アクセストークン/シークレット）のユーザーコンテキスト。
画像付きツイートはAPI v2の create_tweet だけでは完結せず、メディアアップロードだけは
v1.1エンドポイント（tweepy.API.media_upload）を使う必要がある。
Bearer Tokenはアプリ単体認証（読み取り専用用途）のため、ユーザーとして投稿するこの用途では使用しない。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .. import config
from .base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)

# Xの280文字制限はCJK文字を重み2でカウントするため、正確な重み計算はせず
# 安全側に倒した文字数で切り詰める（日本語主体のキャプションを想定）。
MAX_CAPTION_CHARS = 120


def truncate_caption(caption: str, max_chars: int = MAX_CAPTION_CHARS) -> str:
    if len(caption) <= max_chars:
        return caption
    return caption[: max_chars - 1].rstrip() + "…"


class XPublisher(BasePublisher):
    platform = "x"

    def __init__(self, dry_run: bool = True, api=None, client=None):
        super().__init__(dry_run=dry_run)
        self._api = api
        self._client = client

    def _build_clients(self):
        import tweepy

        required = [config.X_API_KEY, config.X_API_SECRET, config.X_ACCESS_TOKEN, config.X_ACCESS_TOKEN_SECRET]
        if not all(required):
            raise RuntimeError("X用の認証情報（APIキー/シークレット/アクセストークン）が設定されていません。")

        auth = tweepy.OAuth1UserHandler(
            config.X_API_KEY,
            config.X_API_SECRET,
            config.X_ACCESS_TOKEN,
            config.X_ACCESS_TOKEN_SECRET,
        )
        api = tweepy.API(auth)
        client = tweepy.Client(
            consumer_key=config.X_API_KEY,
            consumer_secret=config.X_API_SECRET,
            access_token=config.X_ACCESS_TOKEN,
            access_token_secret=config.X_ACCESS_TOKEN_SECRET,
        )
        return api, client

    def _publish(
        self,
        caption: str,
        image_path: Optional[Path] = None,
        image_url: Optional[str] = None,
    ) -> PublishResult:
        if image_path is None:
            raise ValueError("X投稿には画像ファイルのパス（image_path）が必要です。")

        api, client = (self._api, self._client)
        if api is None or client is None:
            api, client = self._build_clients()

        text = truncate_caption(caption)

        media = api.media_upload(filename=str(image_path))
        response = client.create_tweet(text=text, media_ids=[media.media_id])

        tweet_id = None
        data = getattr(response, "data", None)
        if data:
            tweet_id = data.get("id")

        logger.info("Xへ投稿しました: tweet_id=%s", tweet_id)
        return PublishResult(
            platform=self.platform,
            success=True,
            detail="投稿しました。",
            post_id=str(tweet_id) if tweet_id else None,
        )
