"""Gemini画像編集API（通称 Nano Banana 2）を使い、客室写真に人物等を合成する。

「Nano Banana 2」はマーケティング上の通称でAPIのモデルIDではないため、
実際に呼び出すモデル名は config.GEMINI_IMAGE_MODEL の1箇所にまとめてある
（モデル名が変わった場合はここだけ差し替えればよい。実装時に最新のGemini APIドキュメントで要確認）。
"""
from __future__ import annotations

import io
import logging
from typing import Optional

from PIL import Image, ImageStat

from . import config

logger = logging.getLogger(__name__)


class ImageGenerationError(RuntimeError):
    """既定のリトライ回数を尽くしても画像生成に成功しなかった場合。"""


DEFAULT_PROMPT_TEMPLATE = (
    "この客室写真を参照画像として、実在しない架空の人物がくつろいでいる様子を自然に合成してください。"
    "部屋の構造・家具・雰囲気・写真としての品質は保ってください。実在の人物に似せないでください。"
    "テーマ: {keyword}"
)


def _build_client():
    # 遅延import: SDK未インストールでもこのモジュール自体はimportできるようにする（テスト容易性のため）。
    from google import genai

    if not config.GEMINI_API_KEY:
        raise ImageGenerationError("GEMINI_API_KEY が設定されていません。")
    return genai.Client(api_key=config.GEMINI_API_KEY)


def _extract_image(response) -> Optional[Image.Image]:
    """レスポンスのpartsはテキストと画像が混在しうるため、inline_dataを持つ最初のpartを探す。"""
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", None) or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None and getattr(inline_data, "data", None):
                return Image.open(io.BytesIO(inline_data.data))
    return None


def _looks_blank(image: Image.Image) -> bool:
    stat = ImageStat.Stat(image.convert("RGB"))
    return max(stat.stddev) < config.BLANK_IMAGE_STDDEV_THRESHOLD


def _passes_quality_check(image: Image.Image) -> bool:
    if image.width < config.MIN_IMAGE_DIMENSION or image.height < config.MIN_IMAGE_DIMENSION:
        return False
    if _looks_blank(image):
        return False
    return True


def generate_composite_image(
    room_photo: Image.Image,
    keyword: str,
    client=None,
    max_retries: Optional[int] = None,
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE,
) -> Image.Image:
    """room_photoを参照画像としてGeminiに渡し、人物等を合成した画像を返す。

    生成 → 品質チェック（サイズ・単色でないか）→ 失敗時はリトライ、という流れ。
    """
    client = client or _build_client()
    retries = config.GEMINI_MAX_RETRIES if max_retries is None else max_retries
    prompt = prompt_template.format(keyword=keyword)

    last_error: Optional[str] = None
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_IMAGE_MODEL,
                contents=[prompt, room_photo],
            )
        except Exception as exc:  # noqa: BLE001 - SDK側の例外型はバージョンで変わるため広く捕捉して記録する
            last_error = f"API呼び出しに失敗: {exc}"
            logger.warning("Gemini画像生成に失敗（試行 %d/%d）: %s", attempt, retries, exc)
            continue

        image = _extract_image(response)
        if image is None:
            last_error = "レスポンスに画像データが含まれていませんでした（安全フィルタ等でブロックされた可能性）。"
            logger.warning("Gemini画像生成 試行 %d/%d: %s", attempt, retries, last_error)
            continue

        if not _passes_quality_check(image):
            last_error = "生成画像が不自然（サイズ不足または単色に近い）と判定されました。"
            logger.warning("Gemini画像生成 試行 %d/%d: %s", attempt, retries, last_error)
            continue

        return image

    raise ImageGenerationError(
        f"{retries}回試行しましたが画像生成に成功しませんでした。最後のエラー: {last_error}"
    )
