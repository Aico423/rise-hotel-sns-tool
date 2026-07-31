import pytest
from PIL import Image

from rise_sns import caption_overlay, config


def _fixed_width_measure(char_width: float):
    return lambda s: len(s) * char_width


def test_wrap_text_splits_on_width():
    lines = caption_overlay.wrap_text("あいうえおかきくけこ", _fixed_width_measure(1.0), max_width=5.0)
    assert lines == ["あいうえお", "かきくけこ"]


def test_wrap_text_preserves_explicit_newlines():
    lines = caption_overlay.wrap_text("あいう\nえお", _fixed_width_measure(1.0), max_width=10.0)
    assert lines == ["あいう", "えお"]


def test_wrap_text_handles_empty_string():
    lines = caption_overlay.wrap_text("", _fixed_width_measure(1.0), max_width=10.0)
    assert lines == [""]


def test_wrap_text_breaks_on_word_boundaries_not_mid_word():
    # "Bottom" のような英単語の途中で改行されず、単語ごと次の行に送られることを確認する。
    lines = caption_overlay.wrap_text("Top: Wide 155cm /Bottom: King 185cm", _fixed_width_measure(1.0), max_width=20.0)
    assert lines == ["Top: Wide 155cm", "/Bottom: King 185cm"]


def test_wrap_text_splits_overlong_single_word():
    lines = caption_overlay.wrap_text("supercalifragilisticexpialidocious", _fixed_width_measure(1.0), max_width=10.0)
    assert lines == ["supercalif", "ragilistic", "expialidoc", "ious"]


def test_wrap_text_keeps_lone_number_glued_to_following_word():
    # "3" だけが行末に取り残され、次の行が "bedroom," から始まるような読みにくい改行を避ける。
    text = "Queen bed x8, 3 bedroom, Up to 16 pax, Kitchen, cutlery, washing machine, dryer available."
    lines = caption_overlay.wrap_text(text, _fixed_width_measure(1.0), max_width=24.0)
    joined = " ".join(lines)
    assert "3 bedroom," in joined
    assert "16 pax," in joined
    for line in lines:
        assert not line.rstrip().endswith(" 3")
        assert not line.lstrip().startswith("bedroom,")
        assert not line.lstrip().startswith("pax,")


def test_bundled_font_exists_and_works_with_default_path():
    # リポジトリに同梱しているフォント（admin/assets/fonts）が実際に存在し、
    # font_pathを明示しないデフォルト呼び出しでも動くことを確認する
    # （Vercel管理画面・GitHub Actionsの両方でこのデフォルトパスが使われるため）。
    assert config.CAPTION_FONT_PATH.exists()
    canvas = Image.new("RGB", (800, 1200), color=(220, 210, 200))
    photo_box = (0, 0, 800, 700)
    result = caption_overlay.add_caption_below_photo(canvas, photo_box, "客室からの眺めをお楽しみください")
    assert result.size == (800, 1200)
    assert result.mode == "RGB"


def test_add_caption_below_photo_never_draws_over_the_photo_area():
    # 写真の部分（photo_box内）には一切文字を描画しない（写真が見えにくくなる問題を避けるため）。
    photo_color = (10, 20, 200)
    canvas = Image.new("RGB", (800, 1200), color=(230, 225, 215))
    photo_box = (40, 40, 760, 700)
    left, top, right, bottom = photo_box
    for x in range(left, right):
        for y in range(top, bottom):
            canvas.putpixel((x, y), photo_color)

    long_text = "Queen bed×8 3 bedroom Up to 16 pax Kitchen, cutlery, washing machine, dryer available anytime"
    result = caption_overlay.add_caption_below_photo(canvas, photo_box, long_text)

    for x in (left, (left + right) // 2, right - 1):
        for y in (top, (top + bottom) // 2, bottom - 1):
            assert result.getpixel((x, y)) == photo_color


def test_add_caption_below_photo_does_nothing_without_margin():
    canvas = Image.new("RGB", (400, 300), color=(200, 200, 200))
    photo_box = (0, 0, 400, 300)  # 余白が無い（写真がキャンバス全体を占める）
    result = caption_overlay.add_caption_below_photo(canvas, photo_box, "テスト文言")
    assert list(result.getdata()) == list(canvas.getdata())


def test_add_caption_below_photo_ignores_empty_text():
    canvas = Image.new("RGB", (400, 300), color=(200, 200, 200))
    photo_box = (0, 0, 400, 150)
    result = caption_overlay.add_caption_below_photo(canvas, photo_box, "   ")
    assert list(result.getdata()) == list(canvas.getdata())


def test_add_caption_below_photo_raises_clear_error_when_font_missing(tmp_path):
    canvas = Image.new("RGB", (400, 300), color=(0, 0, 0))
    photo_box = (0, 0, 400, 150)
    missing_font = tmp_path / "does-not-exist.ttf"
    with pytest.raises(FileNotFoundError):
        caption_overlay.add_caption_below_photo(canvas, photo_box, "テスト", font_path=missing_font)
