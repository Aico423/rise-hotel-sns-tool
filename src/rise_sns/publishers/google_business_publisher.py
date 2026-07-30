"""Google Business Profile（旧Googleマイビジネス）の「最新情報」投稿。

Business Profile Performance/Posts APIへの書き込みはAPIキーやサービスアカウントではなく
ユーザーのOAuth2（リフレッシュトークン）が必要。また、開発仕様書に記載の通りAPIを有効化しただけでは
使えず、Googleへの個別アクセスリクエスト審査が必要（未承認の間は「見えない審査待ち」でクォータ0）。

【重要】このAPIは一般の第三者アプリへのアクセスがかなり制限されており、
ホテル単体の申請では承認されない可能性がある点をREADMEにも明記している。
そのため本モジュールは完全に実装・単体テスト可能な状態にしつつ、恒久的に無効化されたままでも
運用上問題ない（＝スタッフによる手動投稿を継続する）前提で作られている。

ENABLE_GOOGLE_BUSINESS=true にすると有効化される。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

from .. import config
from .base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
BUSINESS_API_BASE = "https://mybusiness.googleapis.com/v4"


def _refresh_access_token(session) -> str:
    if not all([config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET, config.GOOGLE_REFRESH_TOKEN]):
        raise RuntimeError("Google OAuth用の認証情報（クライアントID/シークレット/リフレッシュトークン）が設定されていません。")

    resp = session.post(
        TOKEN_URI,
        data={
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "refresh_token": config.GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    access_token = resp.json().get("access_token")
    if not access_token:
        raise RuntimeError(f"アクセストークンの取得に失敗しました: {resp.text}")
    return access_token


class GoogleBusinessPublisher(BasePublisher):
    platform = "google"

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
            raise ValueError("Google Business投稿には公開URL（image_url）が必要です。")
        if not config.GOOGLE_BUSINESS_ACCOUNT_ID or not config.GOOGLE_BUSINESS_LOCATION_ID:
            raise RuntimeError("GOOGLE_BUSINESS_ACCOUNT_ID または GOOGLE_BUSINESS_LOCATION_ID が設定されていません。")

        access_token = _refresh_access_token(self._session)

        url = (
            f"{BUSINESS_API_BASE}/accounts/{config.GOOGLE_BUSINESS_ACCOUNT_ID}"
            f"/locations/{config.GOOGLE_BUSINESS_LOCATION_ID}/localPosts"
        )
        payload = {
            "languageCode": "ja",
            "summary": caption,
            "topicType": "STANDARD",
            "media": [{"mediaFormat": "PHOTO", "sourceUrl": image_url}],
        }
        resp = self._session.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        post_name = resp.json().get("name")

        logger.info("Google Businessへ投稿しました: name=%s", post_name)
        return PublishResult(platform=self.platform, success=True, detail="投稿しました。", post_id=post_name)
