"""生成した画像をSNSごとの推奨サイズに変換する。"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageFilter


@dataclass(frozen=True)
class PlatformFormat:
    name: str
    width: int
    height: int
    is_story: bool = False


# 仕様書記載の推奨サイズに準拠
FORMATS: dict[str, PlatformFormat] = {
    "x": PlatformFormat("x", 1600, 900),
    "google": PlatformFormat("google", 720, 720),
    "instagram": PlatformFormat("instagram", 1080, 1920, is_story=True),
    "facebook": PlatformFormat("facebook", 1080, 1920, is_story=True),
}


def _fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """アスペクト比を保ったまま、指定サイズを埋めるように中央でクロップする。"""
    src_ratio = image.width / image.height
    dst_ratio = width / height

    if src_ratio > dst_ratio:
        new_height = height
        new_width = round(new_height * src_ratio)
    else:
        new_width = width
        new_height = round(new_width / src_ratio)

    resized = image.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _make_story_canvas(image: Image.Image, width: int, height: int) -> Image.Image:
    """横長の素材を、ぼかした背景＋中央に収めた本画像で縦長ストーリー用に仕立てる。"""
    background = _fit_cover(image, width, height).filter(ImageFilter.GaussianBlur(30))

    src_ratio = image.width / image.height
    fitted_width = width
    fitted_height = round(fitted_width / src_ratio)
    if fitted_height > height:
        fitted_height = height
        fitted_width = round(fitted_height * src_ratio)
    fitted = image.resize((fitted_width, fitted_height), Image.LANCZOS)

    canvas = background.convert("RGB")
    offset = ((width - fitted_width) // 2, (height - fitted_height) // 2)
    canvas.paste(fitted, offset)
    return canvas


def render_for_platform(image: Image.Image, platform: str) -> Image.Image:
    fmt = FORMATS[platform]
    if fmt.is_story:
        return _make_story_canvas(image, fmt.width, fmt.height)
    return _fit_cover(image, fmt.width, fmt.height)
