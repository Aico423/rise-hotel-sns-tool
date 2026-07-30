"""投稿モジュール共通の基底クラス。

すべての投稿モジュールは dry_run=True（既定）で呼び出すと実際のHTTP通信を一切行わず、
ログに記録するだけの安全な動作になる。Meta/Google Business Profileの審査が下りるまでは
main.py側でこのフラグをTrueのまま渡し続けることで、コードは完成させつつ本番投稿だけを止められる。
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    platform: str
    success: bool
    detail: str
    post_id: Optional[str] = None


class BasePublisher(abc.ABC):
    platform: str = "base"

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def publish(
        self,
        caption: str,
        image_path: Optional[Path] = None,
        image_url: Optional[str] = None,
    ) -> PublishResult:
        if self.dry_run:
            detail = f"[dry-run] {self.platform} への本番投稿はスキップしました（現在は無効化されています）。"
            logger.info(detail)
            return PublishResult(platform=self.platform, success=True, detail=detail)

        try:
            return self._publish(caption=caption, image_path=image_path, image_url=image_url)
        except Exception as exc:  # noqa: BLE001 - 呼び出し元（オーケストレーター）に必ず結果を返すため広く捕捉する
            logger.exception("%s への投稿に失敗しました", self.platform)
            return PublishResult(platform=self.platform, success=False, detail=str(exc))

    @abc.abstractmethod
    def _publish(
        self,
        caption: str,
        image_path: Optional[Path] = None,
        image_url: Optional[str] = None,
    ) -> PublishResult:
        """実際の投稿処理。dry_run=Falseのときだけ呼ばれる。"""
