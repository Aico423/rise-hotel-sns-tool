"""生成画像にキャプション（キーワードを含む文章）をPillowで合成する。

英語は単語（スペース区切り）の途中で改行すると不自然なため、まず単語単位で
折り返しを試みる。日本語のように単語間にスペースが無い文章や、1単語だけで
max_widthを超える場合（英語の長い連続文字列を含む）は、その部分だけ
1文字ずつ足していく貪欲法にフォールバックする（wrap_text はフォント無しでも単体テスト可能）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

from . import config


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
        for word in paragraph.split(" "):
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


def _contrasting_text_color(background_color: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = background_color
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    if luminance > 150:
        return (45, 32, 28)
    return (255, 255, 255)


def add_caption_below_photo(
    canvas: Image.Image,
    photo_box: tuple[int, int, int, int],
    text: str,
    font_path: Optional[Path] = None,
) -> Image.Image:
    """写真の下の余白部分（photo_boxの外側）にだけキャプションを描画する。

    写真そのものの上には一切文字を乗せない（写真が見えにくくなる問題を避けるため）。
    余白の高さに収まるよう、フォントサイズを自動で縮小しながら折り返す。
    """
    font_path = font_path or config.CAPTION_FONT_PATH
    if not font_path.exists():
        raise FileNotFoundError(
            f"日本語フォントが見つかりません: {font_path}\n"
            "GitHub Actionsのワークフローでフォント取得ステップが実行されているか、"
            "ローカルの場合は assets/fonts/ にNoto Sans JPを配置しているか確認してください。"
        )

    if not text.strip():
        return canvas

    width, height = canvas.size
    _, _, _, photo_bottom = photo_box
    margin_top = photo_bottom
    margin_height = height - margin_top
    if margin_height <= 0:
        return canvas

    side_padding = round(width * 0.06)
    vertical_padding = round(margin_height * 0.12)
    max_text_width = width - 2 * side_padding
    max_text_height = margin_height - 2 * vertical_padding

    result = canvas.convert("RGB")
    draw = ImageDraw.Draw(result)

    background_color = result.getpixel((side_padding, margin_top + 1))
    text_color = _contrasting_text_color(background_color)

    max_font_size = max(18, height // 28)
    min_font_size = 16
    font_size, lines = _fit_font_size(
        text, draw, font_path, max_text_width, max_text_height, max_font_size, min_font_size
    )
    font = ImageFont.truetype(str(font_path), font_size)

    line_spacing = int(font_size * 0.35)
    line_height = font_size + line_spacing
    y = margin_top + vertical_padding
    for line in lines:
        draw.text((side_padding, y), line, font=font, fill=text_color)
        y += line_height

    return result
