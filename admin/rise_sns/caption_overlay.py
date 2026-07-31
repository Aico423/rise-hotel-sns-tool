"""生成画像にキャプション（キーワードを含む文章）をPillowで合成する。

英語は単語（スペース区切り）の途中で改行すると不自然なため、まず単語単位で
折り返しを試みる。日本語のように単語間にスペースが無い文章や、1単語だけで
max_widthを超える場合（英語の長い連続文字列を含む）は、その部分だけ
1文字ずつ足していく貪欲法にフォールバックする（wrap_text はフォント無しでも単体テスト可能）。

また、"3 bedroom" "16 pax" のように数字とその直後の単位・単語が離れて改行されると
非常に読みにくくなるため、数字だけの単語とその次の単語は1つの塊として扱い、
行の途中で分断されないようにする。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

from . import config

# "3" "16," "1,000" のように数字（と桁区切りのカンマ・ピリオド）だけで構成される単語にマッチする。
# こういう単語は次に来る単語（単位・名詞）と分離して改行すると読みにくいため、1つの塊として扱う。
_LONE_NUMBER_RE = re.compile(r"^[\d,.\-]+$")


def _group_number_unit_pairs(words: list[str]) -> list[str]:
    """"3", "bedroom," のように連続する数字単語＋次の単語を、1つの折り返し不可能な塊にまとめる。"""
    grouped: list[str] = []
    i = 0
    while i < len(words):
        word = words[i]
        if word and _LONE_NUMBER_RE.match(word) and i + 1 < len(words) and words[i + 1]:
            grouped.append(f"{word} {words[i + 1]}")
            i += 2
        else:
            grouped.append(word)
            i += 1
    return grouped


def _wrap_chars(word: str, measure: Callable[[str], float], max_width: float) -> list[str]:
    """スペースを含まない1つの塊（日本語の文章、または長すぎる英単語）を1文字ずつ折り返す。"""
    lines: list[str] = []
    current = ""
    for ch in word:
        candidate = current + ch
        if current and measure(candidate) > max_width:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def wrap_text(text: str, measure: Callable[[str], float], max_width: float) -> list[str]:
    """measure(部分文字列) が max_width を超えないように、単語の区切り（スペース）を優先して折り返す。"""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for word in _group_number_unit_pairs(paragraph.split(" ")):
            candidate = f"{current} {word}" if current else word
            if measure(candidate) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if measure(word) <= max_width:
                current = word
                continue
            # 1単語だけでmax_widthを超える場合（日本語の文章や長い連続文字列）は文字単位で折り返す
            word_lines = _wrap_chars(word, measure, max_width)
            if word_lines:
                current = word_lines[-1]
                lines.extend(word_lines[:-1])
        if current:
            lines.append(current)
    return lines


def _fit_font_size(
    text: str,
    draw: ImageDraw.ImageDraw,
    font_path: Path,
    max_width: float,
    max_height: float,
    max_size: int,
    min_size: int,
) -> tuple[int, list[str]]:
    """max_width×max_heightの枠に収まる最大のフォントサイズと、折り返し済みの行を返す。

    最小サイズでもまだ収まらない場合は、最小サイズのまま返す（枠からのはみ出しは許容し、
    描画自体が失敗しないようにする）。
    """
    size = max_size
    while size >= min_size:
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap_text(text, lambda s: draw.textlength(s, font=font), max_width)
        line_spacing = int(size * 0.35)
        line_height = size + line_spacing
        if len(lines) * line_height <= max_height:
            return size, lines
        size -= 2
    font = ImageFont.truetype(str(font_path), min_size)
    lines = wrap_text(text, lambda s: draw.textlength(s, font=font), max_width)
    return min_size, lines


def _hex_to_rgb(value: Optional[str], default: tuple[int, int, int]) -> tuple[int, int, int]:
    if not value:
        return default
    text = value.strip().lstrip("#")
    if len(text) != 6:
        return default
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return default


def _font_path_for_weight(weight: Optional[str]) -> Path:
    return config.CAPTION_FONT_WEIGHTS.get(weight or "", config.CAPTION_FONT_WEIGHTS[config.DEFAULT_CAPTION_FONT_WEIGHT])


def _check_fonts_bundled() -> None:
    missing = [str(p) for p in config.CAPTION_FONT_WEIGHTS.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "キャプション用フォントが見つかりません: " + ", ".join(missing) + "\n"
            "admin/assets/fonts/ にPoppinsフォント一式が配置されているか確認してください。"
        )


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    text: str,
    weight: Optional[str],
    bg_color: tuple[int, int, int],
    text_color: tuple[int, int, int],
    font_size: int,
) -> float:
    """角丸バッジ（部屋番号など）を描画し、バッジの下端のy座標を返す。"""
    font = ImageFont.truetype(str(_font_path_for_weight(weight)), font_size)
    pad_x, pad_y = round(font_size * 0.55), round(font_size * 0.32)
    text_width = draw.textlength(text, font=font)
    box = [x, y, x + text_width + pad_x * 2, y + font_size + pad_y * 2]
    radius = (box[3] - box[1]) / 2
    draw.rounded_rectangle(box, radius=radius, fill=bg_color)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=text_color)
    return box[3]


def compose_caption(
    canvas: Image.Image,
    photo_box: tuple[int, int, int, int],
    body_text: str,
    badge_text: Optional[str] = None,
    accent_text: Optional[str] = None,
    style: Optional[dict] = None,
) -> Image.Image:
    """写真の下の余白部分に、部屋番号バッジ→強調ワード→本文の順で装飾付きキャプションを描画する。

    写真そのものの上には一切文字を乗せない（写真が見えにくくなる問題を避けるため）。
    style未指定のキーは config.DEFAULT_TEXT_STYLE の既定値（色・太さ）で補う。
    """
    _check_fonts_bundled()
    merged_style = {**config.DEFAULT_TEXT_STYLE, **(style or {})}
    badge_text = str(badge_text) if badge_text is not None else None
    accent_text = str(accent_text) if accent_text is not None else None

    width, height = canvas.size
    _, _, _, photo_bottom = photo_box
    margin_top = photo_bottom
    margin_height = height - margin_top
    if margin_height <= 0:
        return canvas

    result = canvas.convert("RGB")
    draw = ImageDraw.Draw(result)

    side_padding = round(width * 0.06)
    y = margin_top + round(margin_height * 0.08)
    bottom_limit = height - round(margin_height * 0.05)

    badge_bg = _hex_to_rgb(merged_style.get("badge_bg_color"), (196, 90, 60))
    badge_fg = _hex_to_rgb(merged_style.get("badge_text_color"), (255, 255, 255))
    accent_color = _hex_to_rgb(merged_style.get("accent_color"), (196, 90, 60))
    body_color = _hex_to_rgb(merged_style.get("body_text_color"), (45, 32, 28))

    if badge_text and badge_text.strip():
        badge_font_size = max(24, round(width * 0.041))
        y = _draw_badge(
            draw, side_padding, y, badge_text.strip(), merged_style.get("badge_weight"),
            badge_bg, badge_fg, badge_font_size,
        )
        y += round(margin_height * 0.04)

    if accent_text and accent_text.strip():
        accent_font_size = max(26, round(width * 0.046))
        accent_font = ImageFont.truetype(str(_font_path_for_weight(merged_style.get("accent_weight"))), accent_font_size)
        draw.text((side_padding, y), accent_text.strip(), font=accent_font, fill=accent_color)
        y += accent_font_size + round(margin_height * 0.035)

    if body_text and body_text.strip() and y < bottom_limit:
        max_text_width = width - 2 * side_padding
        max_text_height = bottom_limit - y
        body_font_path = _font_path_for_weight(merged_style.get("body_weight"))
        max_font_size = max(18, height // 28)
        font_size, lines = _fit_font_size(body_text, draw, body_font_path, max_text_width, max_text_height, max_font_size, 16)
        font = ImageFont.truetype(str(body_font_path), font_size)
        line_spacing = int(font_size * 0.35)
        line_height = font_size + line_spacing
        for line in lines:
            draw.text((side_padding, y), line, font=font, fill=body_color)
            y += line_height

    return result
