from rise_sns import text_style


def test_styles_from_config_returns_default_entry_when_nothing_saved():
    styles = text_style.styles_from_config({})
    assert len(styles) == 1
    assert styles[0]["id"] == text_style.DEFAULT_STYLE_ID
    assert styles[0]["is_default"] is True


def test_styles_from_config_migrates_legacy_single_object():
    legacy_config = {"text_style": {"badge_bg_color": "#123456", "badge_weight": "bold"}}
    styles = text_style.styles_from_config(legacy_config)
    assert len(styles) == 1
    assert styles[0]["badge_bg_color"] == "#123456"
    assert styles[0]["is_default"] is True


def test_styles_from_config_prefers_new_list_format():
    config_data = {
        "text_style": {"badge_bg_color": "#000000"},
        "text_styles": [{"id": "a", "name": "A", "is_default": True, "badge_bg_color": "#111111"}],
    }
    styles = text_style.styles_from_config(config_data)
    assert len(styles) == 1
    assert styles[0]["badge_bg_color"] == "#111111"


def test_default_style_returns_the_flagged_entry():
    config_data = {
        "text_styles": [
            {"id": "a", "name": "A", "is_default": False, "badge_bg_color": "#111111"},
            {"id": "b", "name": "B", "is_default": True, "badge_bg_color": "#222222"},
        ]
    }
    assert text_style.default_style(config_data)["id"] == "b"


def test_default_style_falls_back_to_first_entry_when_none_flagged():
    config_data = {"text_styles": [{"id": "a", "name": "A", "badge_bg_color": "#111111"}]}
    assert text_style.default_style(config_data)["id"] == "a"


def test_style_by_id_returns_requested_style():
    config_data = {
        "text_styles": [
            {"id": "a", "name": "A", "is_default": True, "badge_bg_color": "#111111"},
            {"id": "b", "name": "B", "is_default": False, "badge_bg_color": "#222222"},
        ]
    }
    assert text_style.style_by_id(config_data, "b")["id"] == "b"


def test_style_by_id_falls_back_to_default_when_id_missing_or_unknown():
    config_data = {
        "text_styles": [
            {"id": "a", "name": "A", "is_default": True, "badge_bg_color": "#111111"},
        ]
    }
    assert text_style.style_by_id(config_data, None)["id"] == "a"
    assert text_style.style_by_id(config_data, "does-not-exist")["id"] == "a"
