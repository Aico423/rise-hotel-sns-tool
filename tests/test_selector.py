from datetime import date

import pytest

from rise_sns import selector


def make_material(id_, seasons, active=True):
    return {"id": id_, "image_path": f"images/{id_}.jpg", "seasons": seasons, "active": active}


def make_text(id_, platforms=None, active=True, material_ids=None):
    return {
        "id": id_,
        "text": f"text-{id_}",
        "platforms": platforms or {"x": True, "instagram": True, "facebook": True, "google": True},
        "active": active,
        "material_ids": material_ids or [],
    }


def test_current_season_summer():
    assert selector.current_season(date(2026, 7, 30)) == "夏"


def test_current_season_winter():
    assert selector.current_season(date(2026, 1, 15)) == "冬"


def test_select_material_prefers_season_match():
    materials = [
        make_material("summer-room", ["夏"]),
        make_material("winter-room", ["冬"]),
    ]
    chosen = selector.select_material(materials, history=[], today=date(2026, 7, 30))
    assert chosen["id"] == "summer-room"


def test_select_material_falls_back_when_no_season_match():
    materials = [make_material("winter-room", ["冬"])]
    chosen = selector.select_material(materials, history=[], today=date(2026, 7, 30))
    assert chosen["id"] == "winter-room"


def test_select_material_avoids_recent_when_alternative_exists():
    materials = [make_material("a", ["通年"]), make_material("b", ["通年"])]
    history = [{"date": "2026-07-29", "material_id": "a"}]
    chosen = selector.select_material(materials, history, today=date(2026, 7, 30))
    assert chosen["id"] == "b"


def test_select_material_falls_back_to_full_pool_when_all_recent():
    materials = [make_material("a", ["通年"])]
    history = [{"date": "2026-07-29", "material_id": "a"}]
    chosen = selector.select_material(materials, history, today=date(2026, 7, 30))
    assert chosen["id"] == "a"


def test_select_material_ignores_inactive():
    materials = [make_material("a", ["通年"], active=False)]
    with pytest.raises(selector.NoEligibleMaterialError):
        selector.select_material(materials, history=[])


def test_select_text_ignores_inactive():
    texts = [make_text("a", active=False)]
    with pytest.raises(selector.NoEligibleTextError):
        selector.select_text(texts, history=[])


def test_compute_creative_tags_combines_material_and_text_tags():
    material = make_material("a", ["夏", "通年"])
    material["room_type"] = "スイートルーム"
    text = make_text("t1")
    text["category"] = "季節限定"
    text["tags"] = ["東京", "新宿"]

    tags = selector.compute_creative_tags(material, text)
    assert tags == {"スイートルーム", "夏", "通年", "季節限定", "東京", "新宿"}


def test_compute_creative_tags_handles_missing_optional_fields():
    material = {"id": "a", "seasons": []}
    text = {"id": "t1"}
    assert selector.compute_creative_tags(material, text) == set()


def test_select_text_without_material_id_ignores_linking():
    texts = [make_text("a", material_ids=["room-801"])]
    chosen = selector.select_text(texts, history=[])
    assert chosen["id"] == "a"


def test_select_text_with_material_id_excludes_unrelated_linked_text():
    texts = [
        make_text("room-801-text", material_ids=["room-801"]),
        make_text("generic-text"),
    ]
    chosen = selector.select_text(texts, history=[], material_id="room-601")
    assert chosen["id"] == "generic-text"


def test_select_text_with_material_id_includes_matching_linked_text():
    texts = [
        make_text("room-801-text", material_ids=["room-801"]),
        make_text("room-601-text", material_ids=["room-601"]),
    ]
    chosen = selector.select_text(texts, history=[], material_id="room-801")
    assert chosen["id"] == "room-801-text"


def test_select_text_with_material_id_raises_when_only_unrelated_linked_texts_exist():
    texts = [make_text("room-801-text", material_ids=["room-801"])]
    with pytest.raises(selector.NoEligibleTextError):
        selector.select_text(texts, history=[], material_id="room-601")


def test_select_daily_pair_only_pairs_linked_text_with_its_material():
    materials = [make_material("room-801", ["通年"])]
    texts = [
        make_text("wrong-room-text", material_ids=["room-601"]),
        make_text("right-room-text", material_ids=["room-801"]),
    ]
    result = selector.select_daily_pair(materials, texts, history=[], today=date(2026, 7, 30))
    assert result.material["id"] == "room-801"
    assert result.text["id"] == "right-room-text"


def test_select_daily_pair_returns_platforms_for_text():
    materials = [make_material("a", ["通年"])]
    texts = [make_text("t1", platforms={"x": True, "instagram": False, "facebook": False, "google": False})]
    result = selector.select_daily_pair(materials, texts, history=[], today=date(2026, 7, 30))
    assert result.material["id"] == "a"
    assert result.text["id"] == "t1"
    assert result.platforms_for_text == ["x"]
