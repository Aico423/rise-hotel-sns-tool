"""data/ 配下のJSONファイルを読み書きするための薄いヘルパー。

GitHub Actionsのバッチ処理から使う（checkout済みのローカルファイルを直接読み書きする）。
管理画面（Vercel）側は GitHub Contents API 経由で同じファイルを操作するため、
このモジュールとは別実装（admin/api/github_client.py）を持つ。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_config() -> dict:
    return _read_json(config.CONFIG_PATH)


def load_materials() -> list[dict]:
    data = _read_json(config.MATERIALS_PATH)
    return list(data.get("materials", []))


def load_texts() -> list[dict]:
    data = _read_json(config.TEXTS_PATH)
    return list(data.get("texts", []))


def load_post_history() -> list[dict]:
    data = _read_json(config.POST_HISTORY_PATH)
    return list(data.get("history", []))


def append_post_history(entry: dict) -> None:
    data = _read_json(config.POST_HISTORY_PATH)
    data.setdefault("history", []).append(entry)
    _write_json(config.POST_HISTORY_PATH, data)


def resolve_image_path(image_path: str) -> Path:
    """materials.json内の相対パス（例: "images/xxxx.jpg"）をローカル絶対パスに変換する。"""
    return config.DATA_DIR / image_path
