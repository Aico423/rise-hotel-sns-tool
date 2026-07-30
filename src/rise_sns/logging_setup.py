"""標準出力へのロギング設定（GitHub Actionsのジョブログにそのまま表示される）。"""
from __future__ import annotations

import logging


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
