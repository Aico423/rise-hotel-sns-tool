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


def test_normalize_for_latin_font_converts_fullwidth_ascii_to_halfwidth():
    # Poppins（欧文専用フォント）には全角記号のグリフが無く文字化けするため、
    # "：" "／" 等の全角ASCII相当の文字は半角に正規化する。
    result = caption_overlay._normalize_for_latin_font("Top：Wide-Double 155cm×200cm／Bottom：King")
    assert result == "Top:Wide-Double 155cm×200cm/Bottom:King"


def test_normalize_for_latin_font_replaces_emoji_with_hyphen():
    # Poppins（欧文専用フォント）は絵文字のグリフを持たず豆腐（四角）として表示されるため、
    # 安全に表示できる記号（-）へ置き換える。
    result = caption_overlay._normalize_for_latin_font("📍Godzilla Head\n📍Kabukicho")
    assert result == "- Godzilla Head\n- Kabukicho"
    assert "\U0001F4CD" not in result


def test_compose_caption_normalizes_fullwidth_punctuation_in_all_text_parts():
    canvas = Image.new("RGB", (1080, 1920), color=(230, 225, 215))
    photo_box = (0, 0, 1080, 1100)
    result = caption_overlay.compose_caption(
        canvas, photo_box, "Top：Wide-Double 155cm×200cm", badge_text="601", accent_text="Up to 10 pax"
    )
    assert result.size == (1080, 1920)


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


def test_bundled_fonts_exist_and_work_with_default_style():
    # リポジトリに同梱しているPoppinsフォント一式（admin/assets/fonts）が実際に存在し、
    # styleを明示しないデフォルト呼び出しでも動くことを確認する
    # （Vercel管理画面・GitHub Actionsの両方でこのデフォルトパスが使われるため）。
    for path in config.CAPTION_FONT_WEIGHTS.values():
        assert path.exists()
    canvas = Image.new("RGB", (1080, 1920), color=(220, 210, 200))
    photo_box = (0, 0, 1080, 1100)
    result = caption_overlay.compose_caption(
        canvas, photo_box, "Please enjoy the view from your room", badge_text="601", accent_text="Up to 8 pax"
    )
    assert result.size == (1080, 1920)
    assert result.mode == "RGB"


def test_compose_caption_never_draws_over_the_photo_area():
    # 写真の部分（photo_box内）には一切文字を描画しない（写真が見えにくくなる問題を避けるため）。
    photo_color = (10, 20, 200)
    canvas = Image.new("RGB", (1080, 1920), color=(230, 225, 215))
    photo_box = (40, 40, 1040, 1100)
    left, top, right, bottom = photo_box
    for x in range(left, right):
        for y in range(top, bottom):
            canvas.putpixel((x, y), photo_color)

    long_text = "Queen bed×8 3 bedroom Kitchen, cutlery, washing machine, dryer available anytime"
    result = caption_overlay.compose_caption(canvas, photo_box, long_text, badge_text="601", accent_text="Up to 16 pax")

    for x in (left, (left + right) // 2, right - 1):
        for y in (top, (top + bottom) // 2, bottom - 1):
            assert result.getpixel((x, y)) == photo_color


def test_compose_caption_does_nothing_without_margin():
    canvas = Image.new("RGB", (400, 300), color=(200, 200, 200))
    photo_box = (0, 0, 400, 300)  # 余白が無い（写真がキャンバス全体を占める）
    result = caption_overlay.compose_caption(canvas, photo_box, "テスト文言", badge_text="601")
    assert list(result.getdata()) == list(canvas.getdata())


def test_compose_caption_ignores_empty_text_and_optional_parts():
    canvas = Image.new("RGB", (400, 300), color=(200, 200, 200))
    photo_box = (0, 0, 400, 150)
    result = caption_overlay.compose_caption(canvas, photo_box, "   ")
    assert list(result.getdata()) == list(canvas.getdata())


def test_compose_caption_draws_badge_with_configured_colors():
    canvas = Image.new("RGB", (1080, 1920), color=(230, 225, 215))
    photo_box = (0, 0, 1080, 1100)
    style = {"badge_bg_color": "#112233", "badge_text_color": "#ffffff", "badge_weight": "bold"}
    result = caption_overlay.compose_caption(canvas, photo_box, "body text", badge_text="601", style=style)
    # バッジの中央あたり（角丸の影響を受けない位置）の画素が、指定した背景色に塗られていることを確認する
    side_padding = round(1080 * 0.06)
    margin_top = 1100
    badge_top = margin_top + round((1920 - margin_top) * 0.08)
    badge_font_size = max(24, round(1080 * 0.041))
    badge_height = badge_font_size + 2 * round(badge_font_size * 0.32)
    sample_x = side_padding + round(badge_height / 2)  # 角丸の半径ぶん内側なら必ず塗りつぶし範囲
    sample_y = badge_top + round(badge_height / 2)
    assert result.getpixel((sample_x, sample_y)) == (0x11, 0x22, 0x33)


def test_compose_caption_raises_clear_error_when_fonts_missing(monkeypatch, tmp_path):
    canvas = Image.new("RGB", (400, 300), color=(0, 0, 0))
    photo_box = (0, 0, 400, 150)
    missing = tmp_path / "does-not-exist.ttf"
    monkeypatch.setattr(config, "CAPTION_FONT_WEIGHTS", {"regular": missing})
    monkeypatch.setattr(config, "DEFAULT_CAPTION_FONT_WEIGHT", "regular")
    with pytest.raises(FileNotFoundError):
        caption_overlay.compose_caption(canvas, photo_box, "テスト")
