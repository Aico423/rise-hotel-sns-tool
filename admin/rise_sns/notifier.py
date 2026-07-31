"""失敗時のSlack通知。SLACK_WEBHOOK_URLが未設定なら何もしない（ログにのみ残す）。"""
from __future__ import annotations

import logging

import requests

from . import config

logger = logging.getLogger(__name__)


def notify_failure(message: str) -> None:
    if not config.SLACK_WEBHOOK_URL:
        logger.info("SLACK_WEBHOOK_URL未設定のため通知はスキップします: %s", message)
        return
    try:
        requests.post(config.SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
    except Exception:  # noqa: BLE001 - 通知の失敗でバッチ全体を落としたくないため広く捕捉する
        logger.exception("Slackへの通知送信に失敗しました")
