"""毎日の投稿に使う「客室写真」と「投稿文言」の組み合わせを選ぶロジック。

- 現在の季節に合うタグを優先する（合うものが無ければ全素材から選ぶ）
- 直近 N 日以内に使った素材・文言はできるだけ避ける（プールが尽きたら全体から選び直す）
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from typing import Optional

from . import config

_SEASON_BY_MONTH = {
    12: "冬", 1: "冬", 2: "冬",
    3: "春", 4: "春", 5: "春",
    6: "夏", 7: "夏", 8: "夏",
    9: "秋", 10: "秋", 11: "秋",
}


class NoEligibleMaterialError(RuntimeError):
    """登録済みの客室写真の中から投稿に使えるものが1件も無い場合。"""


class NoEligibleTextError(RuntimeError):
    """登録済みの投稿文言の中から使えるものが1件も無い場合。"""


def current_season(today: Optional[date] = None) -> str:
    today = today or date.today()
    return _SEASON_BY_MONTH[today.month]


def _recent_ids(history: list[dict], key: str, today: date, lookback_days: int) -> set[str]:
    recent: set[str] = set()
    for entry in history:
        try:
            entry_date = date.fromisoformat(entry["date"])
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= (today - entry_date).days <= lookback_days:
            value = entry.get(key)
            if value:
                recent.add(value)
    return recent


def select_material(materials: list[dict], history: list[dict], today: Optional[date] = None) -> dict:
    today = today or date.today()
    active = [m for m in materials if m.get("active", True)]
    if not active:
        raise NoEligibleMaterialError("有効な客室写真が登録されていません。")

    season = current_season(today)
    season_matched = [
        m for m in active
        if season in m.get("seasons", []) or "通年" in m.get("seasons", [])
    ]
    pool = season_matched or active

    recent_ids = _recent_ids(history, "material_id", today, config.POST_HISTORY_LOOKBACK_DAYS)
    fresh_pool = [m for m in pool if m.get("id") not in recent_ids]
    candidates = fresh_pool or pool

    return random.choice(candidates)


def _text_applies_to_material(text: dict, material_id: str) -> bool:
    """material_idsが未設定・空の文言はどの写真にも使える汎用文言として扱う。"""
    material_ids = text.get("material_ids") or []
    return not material_ids or material_id in material_ids


def _text_supports_platforms(text: dict, required_platforms: list[str]) -> bool:
    platforms = text.get("platforms") or {}
    return all(platforms.get(p) for p in required_platforms)


def select_text(
    texts: list[dict],
    history: list[dict],
    today: Optional[date] = None,
    material_id: Optional[str] = None,
    required_platforms: Optional[list[str]] = None,
) -> dict:
    """material_idを指定すると、その写真に紐づけられた文言（または汎用文言）だけから選ぶ。

    これにより「8人部屋の写真」に「2人部屋の文言」が付く、といった内容の不一致を防ぐ。

    required_platformsを指定すると、それらすべての投稿先にチェックが入っている文言だけに
    絞り込む。実際に本番投稿が有効なプラットフォーム（例: X）を指定しておくことで、
    「本文が長すぎるのでXにはチェックを入れていない文言」が選ばれて、その日Xだけ
    投稿されない、という事態を避けられる。
    """
    today = today or date.today()
    active = [t for t in texts if t.get("active", True)]
    if material_id is not None:
        active = [t for t in active if _text_applies_to_material(t, material_id)]
    if not active:
        raise NoEligibleTextError("この写真に使える投稿文言が登録されていません。")

    if required_platforms:
        eligible = [t for t in active if _text_supports_platforms(t, required_platforms)]
        if not eligible:
            names = "・".join(required_platforms)
            raise NoEligibleTextError(f"投稿先に「{names}」を指定した文言（この写真向け）が見つかりませんでした。")
        active = eligible

    recent_ids = _recent_ids(history, "text_id", today, config.POST_HISTORY_LOOKBACK_DAYS)
    fresh_pool = [t for t in active if t.get("id") not in recent_ids]
    candidates = fresh_pool or active

    return random.choice(candidates)


@dataclass
class DailySelection:
    material: dict
    text: dict
    platforms_for_text: list[str]


def compute_creative_tags(material: dict, text: dict) -> set[str]:
    """スタンプ・ハッシュタグ画像の自動選定に使う「その日のクリエイティブのタグ集合」を作る。"""
    tags: set[str] = set()
    if material.get("room_type"):
        tags.add(material["room_type"])
    tags.update(material.get("seasons", []))
    if text.get("category"):
        tags.add(text["category"])
    tags.update(text.get("tags", []))
    return tags


def select_daily_pair(
    materials: list[dict],
    texts: list[dict],
    history: list[dict],
    today: Optional[date] = None,
    required_platforms: Optional[list[str]] = None,
) -> DailySelection:
    today = today or date.today()
    material = select_material(materials, history, today)
    text = select_text(
        texts, history, today, material_id=material.get("id"), required_platforms=required_platforms
    )
    platforms_for_text = [
        platform for platform, enabled in text.get("platforms", {}).items() if enabled
    ]
    return DailySelection(material=material, text=text, platforms_for_text=platforms_for_text)
