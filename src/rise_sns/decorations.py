"""スタンプ・ハッシュタグ画像などの装飾素材を、タグの一致に基づいて自動選定し画像に合成する。

「BOOK NOW」のような予約訴求スタンプや、地名・キャンペーンのハッシュタグ風グラフィックを
あらかじめタグ付きで登録しておき（管理画面の「スタンプ・ハッシュタグ画像」登録）、
その日選ばれた客室写真・投稿文言のタグと1つでも一致するものを、配置場所（四隅・上下中央）ごとに
1つずつ自動選定して画像に焼き込む。

Instagram/FacebookのGraph APIではネイティブのインタラクティブスタンプ（タップ可能なリンク等）は
追加できないため、これは「投稿前の画像そのものに視覚的な装飾として焼き込む」方式で実現している。
"""
from __future__ import annotations

import random
from typing import Callable

from PIL import Image

PLACEMENTS = ("top_left", "top_right", "top_center", "bottom_left", "bottom_right", "bottom_center")

# 画像の短辺に対するスタンプの最大サイズ比率、および余白の比率
MAX_STAMP_RATIO = 0.24
PADDING_RATIO = 0.04


def select_decorations(decorations: list[dict], creative_tags: set[str]) -> list[dict]:
    """配置ゾーンごとに、タグが1つでも一致する装飾からランダムに1つ選ぶ。

    一致するものが無いゾーンには何も挿入しない（無関係なスタンプを無理に出さないため）。
    """
    by_placement: dict[str, list[dict]] = {}
    for decoration in decorations:
        if not decoration.get("active", True):
            continue
        if not set(decoration.get("tags", [])) & creative_tags:
            continue
        placement = decoration.get("placement")
        if placement in PLACEMENTS:
            by_placement.setdefault(placement, []).append(decoration)

    return [random.choice(candidates) for candidates in by_placement.values()]


def _resize_stamp(stamp: Image.Image, base_size: tuple[int, int]) -> Image.Image:
    short_edge = min(base_size)
    max_dim = int(short_edge * MAX_STAMP_RATIO)
    ratio = min(max_dim / stamp.width, max_dim / stamp.height, 1.0)
    if ratio < 1.0:
        new_size = (max(1, round(stamp.width * ratio)), max(1, round(stamp.height * ratio)))
        stamp = stamp.resize(new_size, Image.LANCZOS)
    return stamp


def _position_for(placement: str, base_size: tuple[int, int], stamp_size: tuple[int, int], padding: int) -> tuple[int, int]:
    base_w, base_h = base_size
    stamp_w, stamp_h = stamp_size
    x_positions = {"left": padding, "right": base_w - stamp_w - padding, "center": (base_w - stamp_w) // 2}
    y_positions = {"top": padding, "bottom": base_h - stamp_h - padding, "center": (base_h - stamp_h) // 2}

    vertical, horizontal = placement.split("_")
    return x_positions[horizontal], y_positions[vertical]


def apply_decorations(
    image: Image.Image,
    decorations: list[dict],
    open_stamp: Callable[[dict], Image.Image],
) -> Image.Image:
    """選定済みの装飾画像を合成する。open_stampは装飾のdictを受け取りPIL.Imageを返す関数（呼び出し側がファイル読み込みを注入する）。"""
    base = image.convert("RGBA")
    padding = int(min(base.size) * PADDING_RATIO)

    for decoration in decorations:
        stamp = open_stamp(decoration).convert("RGBA")
        stamp = _resize_stamp(stamp, base.size)
        position = _position_for(decoration["placement"], base.size, stamp.size, padding)
        base.alpha_composite(stamp, dest=position)

    return base.convert("RGB")
