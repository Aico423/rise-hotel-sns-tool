"""文字装飾パターン（config.json の text_styles）の読み取りヘルパー。

スタッフは管理画面の「文字の装飾の設定」から、複数の配色・太さの組み合わせ
（パターン）を登録できる。1つを「既定」に指定でき、自動投稿（毎日のバッチ処理）は
常に既定のパターンを使う。プレビュー画面ではスタッフがその都度好きなパターンを
選んで見え方を比較できる。

旧バージョンでは text_style というパターン1件ぶんのオブジェクトのみを保存していたため、
その形式のデータしか無い場合はここでリスト形式に変換して扱う（後方互換）。
"""
from __future__ import annotations

from . import config

DEFAULT_STYLE_ID = "default"


def _default_entry() -> dict:
    return {"id": DEFAULT_STYLE_ID, "name": "デフォルト", "is_default": True, **config.DEFAULT_TEXT_STYLE}


def styles_from_config(config_data: dict) -> list[dict]:
    styles = config_data.get("text_styles")
    if styles:
        return styles
    legacy = config_data.get("text_style")
    if legacy:
        return [{"id": DEFAULT_STYLE_ID, "name": "デフォルト", "is_default": True, **legacy}]
    return [_default_entry()]


def default_style(config_data: dict) -> dict:
    styles = styles_from_config(config_data)
    return next((s for s in styles if s.get("is_default")), styles[0])


def style_by_id(config_data: dict, style_id: str | None) -> dict:
    styles = styles_from_config(config_data)
    if style_id:
        found = next((s for s in styles if s.get("id") == style_id), None)
        if found:
            return found
    return default_style(config_data)
