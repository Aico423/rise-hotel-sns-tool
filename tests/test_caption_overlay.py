from pathlib import Path

import pytest
from PIL import Image

from rise_sns import caption_overlay

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


@pytest.mark.skipif(not _WINDOWS_TEST_FONT.exists(), reason="Windows同梱フォントが無い環境ではスキップ")
def test_add_caption_returns_same_size_rgb_image():
    base = Image.new("RGB", (800, 600), color=(120, 120, 120))
    result = caption_overlay.add_caption(base, "夜景が自慢のスイートルーム", font_path=_WINDOWS_TEST_FONT)
    assert result.size == (800, 600)
    assert result.mode == "RGB"


def test_add_caption_raises_clear_error_when_font_missing(tmp_path):
    base = Image.new("RGB", (400, 300), color=(0, 0, 0))
    missing_font = tmp_path / "does-not-exist.ttf"
    with pytest.raises(FileNotFoundError):
        caption_overlay.add_caption(base, "テスト", font_path=missing_font)
