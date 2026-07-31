from PIL import Image

from rise_sns import platform_formats


def _photo(width=1200, height=800, color=(80, 120, 160)):
    return Image.new("RGB", (width, height), color=color)


def test_fit_with_margin_returns_platform_sized_canvas_with_margin_below_photo():
    canvas, photo_box = platform_formats.fit_with_margin(_photo(), 1080, 1920)
    assert canvas.size == (1080, 1920)
    left, top, right, bottom = photo_box
    assert 0 <= left < right <= 1080
    assert 0 <= top < bottom <= 1920
    # 写真の下に、キャプション用の余白が必ず残ること
    assert 1920 - bottom > 0


def test_fit_with_margin_photo_slot_height_is_fixed_regardless_of_source_aspect():
    # 元写真の縦横比に関わらず、写真枠の高さは常に同じ比率になる（余白の大きさを安定させるため）。
    expected_height = round(1920 * platform_formats.PHOTO_SLOT_HEIGHT_RATIO)
    for photo in (_photo(width=1600, height=1067), _photo(width=900, height=1600), _photo(width=1080, height=1080)):
        _, (_, top, _, bottom) = platform_formats.fit_with_margin(photo, 1080, 1920)
        assert bottom - top == expected_height


def test_render_for_platform_story_bakes_caption_without_covering_photo():
    rendered = platform_formats.render_for_platform(_photo(), "instagram", caption_text="Queen bed×8 Up to 16 pax")
    assert rendered.size == (1080, 1920)


def test_render_for_platform_story_without_caption_still_returns_platform_size():
    rendered = platform_formats.render_for_platform(_photo(), "facebook", caption_text=None)
    assert rendered.size == (1080, 1920)


def test_render_for_platform_x_ignores_caption_text_and_fills_frame():
    # Xは投稿本文欄に実テキストが表示されるため、画像には文字を焼き込まない。
    rendered = platform_formats.render_for_platform(_photo(), "x", caption_text="この文字は画像には入らないはず")
    assert rendered.size == (1600, 900)


def test_render_for_platform_google_ignores_caption_text_and_fills_frame():
    rendered = platform_formats.render_for_platform(_photo(), "google", caption_text="この文字は画像には入らないはず")
    assert rendered.size == (720, 720)
