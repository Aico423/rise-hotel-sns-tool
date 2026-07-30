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


def select_text(texts: list[dict], history: list[dict], today: Optional[date] = None) -> dict:
    today = today or date.today()
    active = [t for t in texts if t.get("active", True)]
    if not active:
        raise NoEligibleTextError("投稿に使える文言が登録されていません。")

    recent_ids = _recent_ids(history, "text_id", today, config.POST_HISTORY_LOOKBACK_DAYS)
    fresh_pool = [t for t in active if t.get("id") not in recent_ids]
    candidates = fresh_pool or active

    return random.choice(candidates)


@dataclass
class DailySelection:
    material: dict
    text: dict
    platforms_for_text: list[str]


def select_daily_pair(
    materials: list[dict],
    texts: list[dict],
    history: list[dict],
    today: Optional[date] = None,
) -> DailySelection:
    today = today or date.today()
    material = select_material(materials, history, today)
    text = select_text(texts, history, today)
    platforms_for_text = [
        platform for platform, enabled in text.get("platforms", {}).items() if enabled
    ]
    return DailySelection(material=material, text=text, platforms_for_text=platforms_for_text)
