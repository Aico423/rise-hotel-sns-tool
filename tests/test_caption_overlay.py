from pathlib import Path

import pytest
from PIL import Image

from rise_sns import caption_overlay, config

# CIのUbuntuランナーには無いWindows同梱フォント。ローカルWindows開発機でのみ実描画テストを行う。
_WINDOWS_TEST_FONT = Path(r"C:\Windows\Fonts\meiryo.ttc")


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


@pytest.mark.skipif(not _WINDOWS_TEST_FONT.exists(), reason="Windows同梱フォントが無い環境ではスキップ")
def test_add_caption_returns_same_size_rgb_image():
    base = Image.new("RGB", (800, 600), color=(120, 120, 120))
    result = caption_overlay.add_caption(base, "夜景が自慢のスイートルーム", font_path=_WINDOWS_TEST_FONT)
    assert result.size == (800, 600)
    assert result.mode == "RGB"


def test_bundled_font_exists_and_works_with_default_path():
    # リポジトリに同梱しているフォント（admin/assets/fonts）が実際に存在し、
    # font_pathを明示しないデフォルト呼び出しでも動くことを確認する
    # （Vercel管理画面・GitHub Actionsの両方でこのデフォルトパスが使われるため）。
    assert config.CAPTION_FONT_PATH.exists()
    base = Image.new("RGB", (800, 600), color=(90, 90, 90))
    result = caption_overlay.add_caption(base, "客室からの眺めをお楽しみください")
    assert result.size == (800, 600)
    assert result.mode == "RGB"


def test_add_caption_raises_clear_error_when_font_missing(tmp_path):
    base = Image.new("RGB", (400, 300), color=(0, 0, 0))
    missing_font = tmp_path / "does-not-exist.ttf"
    with pytest.raises(FileNotFoundError):
        caption_overlay.add_caption(base, "テスト", font_path=missing_font)
