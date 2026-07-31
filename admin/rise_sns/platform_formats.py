"""生成した画像をSNSごとの推奨サイズに変換する。

Instagram/Facebookのストーリーズは、Graph API経由では画像とは別に文字を表示する仕組みが無いため
（キャプション欄はストーリーズには表示されない）、投稿文章を見せるには画像そのものに焼き込む
しかない。ただし文字を写真の上に直接重ねると写真が見えにくくなるため、写真を余白付きで
縮小して配置し、その余白部分（写真の外）にだけ文字を描画する方式にしている
（caption_overlay.compose_caption が実際の描画を担当する）。

一方、Xの投稿本文・Googleビジネスプロフィールの投稿の説明文は、SNS側の実テキスト欄に
そのまま表示されるため、画像に文字を焼き込む必要が無い（焼き込むと二重表示になってしまう）。
そのため、Xとgoogleの画像は写真をそのまま使う（キャプションは合成しない）。
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from . import caption_overlay


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

# 写真の左右・上部に確保する余白の比率（写真を「カード」のように少し浮かせて見せる）
PHOTO_SIDE_PADDING_RATIO = 0.04
PHOTO_TOP_PADDING_RATIO = 0.04
# 写真の枠（スロット）の高さの比率。元の写真の縦横比に関わらずこの高さで統一する
# （contain方式で余白なしに収めようとすると、横長の写真では下に不自然な余白が
# 大量に余ってしまうため、写真側は決まった大きさの枠にきっちり収める＝はみ出す部分は
# 中央基準でクロップする方式にしている。これによりキャプション欄の高さも常に安定する）。
PHOTO_SLOT_HEIGHT_RATIO = 0.58
# 背景色を写真の平均色に寄せつつ、白側に混ぜて文字が読みやすい明るさにする度合い
BACKGROUND_SOFTEN_RATIO = 0.55


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


def _average_color(image: Image.Image) -> tuple[int, int, int]:
    small = image.convert("RGB").resize((20, 20))
    pixels = list(small.getdata())
    count = len(pixels)
    r = sum(p[0] for p in pixels) // count
    g = sum(p[1] for p in pixels) // count
    b = sum(p[2] for p in pixels) // count
    return (r, g, b)


def _background_color_for(image: Image.Image) -> tuple[int, int, int]:
    """写真の色味に合わせた、キャプション欄用の柔らかい背景色を作る（白寄りに混ぜて可読性を確保）。"""
    r, g, b = _average_color(image)
    return (
        round(r + (255 - r) * BACKGROUND_SOFTEN_RATIO),
        round(g + (255 - g) * BACKGROUND_SOFTEN_RATIO),
        round(b + (255 - b) * BACKGROUND_SOFTEN_RATIO),
    )


def fit_with_margin(image: Image.Image, width: int, height: int) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """写真を上寄せの決まった大きさの枠にきっちり収め（はみ出す部分は中央基準でクロップ）、
    下に必ずキャプション用の余白が残る形のキャンバスを作る。

    戻り値は (キャンバス, 写真の矩形(left, top, right, bottom)) 。
    余白の背景色は写真の平均色から自動生成する。
    """
    background_color = _background_color_for(image)
    canvas = Image.new("RGB", (width, height), background_color)

    side_padding = round(width * PHOTO_SIDE_PADDING_RATIO)
    top_padding = round(height * PHOTO_TOP_PADDING_RATIO)
    slot_width = width - 2 * side_padding
    slot_height = round(height * PHOTO_SLOT_HEIGHT_RATIO)

    fitted = _fit_cover(image, slot_width, slot_height)
    canvas.paste(fitted, (side_padding, top_padding))
    return canvas, (side_padding, top_padding, side_padding + slot_width, top_padding + slot_height)


def render_for_platform(
    image: Image.Image,
    platform: str,
    caption_text: str | None = None,
    badge_text: str | None = None,
    accent_text: str | None = None,
    text_style: dict | None = None,
) -> Image.Image:
    """SNSごとのサイズに変換する。

    caption_text・badge_text・accent_textは、画像に文字を焼き込む必要があるプラットフォーム
    （ストーリーズ形式のInstagram/Facebook）でのみ使われる。badge_textは部屋番号などを角丸バッジで、
    accent_textは最大宿泊人数などをアクセントカラーの強調テキストとして、caption_textはそれ以外の
    詳細文を本文として描画する。X・Googleビジネスプロフィールは実テキストの投稿本文欄に表示されるため、
    ここでは無視して写真をそのまま使う。
    """
    fmt = FORMATS[platform]
    if not fmt.is_story:
        return _fit_cover(image, fmt.width, fmt.height)

    canvas, photo_box = fit_with_margin(image, fmt.width, fmt.height)
    if caption_text or badge_text or accent_text:
        canvas = caption_overlay.compose_caption(
            canvas, photo_box, caption_text or "", badge_text=badge_text, accent_text=accent_text, style=text_style
        )
    return canvas
