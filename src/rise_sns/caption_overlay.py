"""生成画像にキャプション（キーワードを含む文章）をPillowで合成する。

日本語は単語間にスペースが無いため textwrap は使えない。実際の描画幅を測りながら
1文字ずつ足していく貪欲法で折り返す（wrap_text はフォント無しでも単体テスト可能）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

from . import config


def wrap_text(text: str, measure: Callable[[str], float], max_width: float) -> list[str]:
    """measure(部分文字列) が max_width を超えないように、改行位置で分割する。"""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            candidate = current + ch
            if current and measure(candidate) > max_width:
                lines.append(current)
                current = ch
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def add_caption(
    image: Image.Image,
    text: str,
    font_path: Optional[Path] = None,
    font_size: Optional[int] = None,
) -> Image.Image:
    """画像下部に半透明の帯を敷き、その上に白文字でキャプションを描画した新しい画像を返す。"""
    font_path = font_path or config.CAPTION_FONT_PATH
    if not font_path.exists():
        raise FileNotFoundError(
            f"日本語フォントが見つかりません: {font_path}\n"
            "GitHub Actionsのワークフローでフォント取得ステップが実行されているか、"
            "ローカルの場合は assets/fonts/ にNoto Sans JPを配置しているか確認してください。"
        )

    base = image.convert("RGBA")
    width, height = base.size
    resolved_font_size = font_size or max(24, width // 20)
    font = ImageFont.truetype(str(font_path), resolved_font_size)

    measure_draw = ImageDraw.Draw(base)
    max_text_width = width * 0.86

    def measure(s: str) -> float:
        return measure_draw.textlength(s, font=font)

    lines = wrap_text(text, measure, max_text_width)

    line_spacing = int(resolved_font_size * 0.4)
    line_height = resolved_font_size + line_spacing
    block_height = len(lines) * line_height + line_spacing
    band_top = max(0, height - block_height - int(resolved_font_size * 0.6))

    band = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle([0, band_top, width, height], fill=(0, 0, 0, 150))
    composited = Image.alpha_composite(base, band)

    draw = ImageDraw.Draw(composited)
    y = band_top + line_spacing
    for line in lines:
        line_width = measure(line)
        x = (width - line_width) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    return composited.convert("RGB")
