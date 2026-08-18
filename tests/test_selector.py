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


def test_select_platform_pair_only_pairs_linked_text_with_its_material():
    materials = [make_material("room-801", ["通年"])]
    texts = [
        make_text("wrong-room-text", material_ids=["room-601"]),
        make_text("right-room-text", material_ids=["room-801"]),
    ]
    result = selector.select_platform_pair(materials, texts, history=[], platform="x", today=date(2026, 7, 30))
    assert result.material["id"] == "room-801"
    assert result.text["id"] == "right-room-text"


def test_select_platform_pair_only_requires_its_own_platform_checkbox():
    materials = [make_material("a", ["通年"])]
    texts = [make_text("t1", platforms={"x": True, "instagram": False, "facebook": False, "google": False})]
    result = selector.select_platform_pair(materials, texts, history=[], platform="x", today=date(2026, 7, 30))
    assert result.material["id"] == "a"
    assert result.text["id"] == "t1"


def test_select_platform_pair_raises_when_its_own_platform_checkbox_is_missing():
    materials = [make_material("a", ["通年"])]
    texts = [make_text("t1", platforms={"x": False, "instagram": True, "facebook": True, "google": True})]
    with pytest.raises(selector.NoEligibleTextError):
        selector.select_platform_pair(materials, texts, history=[], platform="x", today=date(2026, 7, 30))


def test_select_platform_pair_lets_different_platforms_pick_different_material_and_text():
    # Xとinstagramが同じ写真・同じ文言を使う必要はない
    materials = [
        make_material("room-a", ["通年"]),
        make_material("room-b", ["通年"]),
    ]
    texts = [
        make_text("x-text", platforms={"x": True, "instagram": False, "facebook": False, "google": False}),
        make_text("ig-text", platforms={"x": False, "instagram": True, "facebook": False, "google": False}),
    ]
    x_result = selector.select_platform_pair(materials, texts, history=[], platform="x", today=date(2026, 7, 30))
    ig_result = selector.select_platform_pair(materials, texts, history=[], platform="instagram", today=date(2026, 7, 30))
    assert x_result.text["id"] == "x-text"
    assert ig_result.text["id"] == "ig-text"


def test_select_material_recency_is_scoped_per_platform():
    # xが昨日room-aを使っていても、instagramはroom-aを避ける必要はない
    materials = [make_material("room-a", ["通年"]), make_material("room-b", ["通年"])]
    history = [{"date": "2026-07-29", "posts": {"x": {"material_id": "room-a", "text_id": "t"}}}]
    chosen_for_x = selector.select_material(materials, history, today=date(2026, 7, 30), platform="x")
    assert chosen_for_x["id"] == "room-b"
    chosen_for_instagram = selector.select_material(materials, history, today=date(2026, 7, 30), platform="instagram")
    assert chosen_for_instagram["id"] in {"room-a", "room-b"}


def test_select_material_recency_understands_legacy_shared_history_entries():
    # プラットフォームごとの選択に対応する前の履歴（1日1組を全プラットフォーム共通で使っていた形式）も
    # 引き続き「そのプラットフォームが直近使った」ものとして扱う
    materials = [make_material("room-a", ["通年"]), make_material("room-b", ["通年"])]
    history = [{"date": "2026-07-29", "material_id": "room-a", "platforms_posted": ["x"]}]
    chosen_for_x = selector.select_material(materials, history, today=date(2026, 7, 30), platform="x")
    assert chosen_for_x["id"] == "room-b"
    chosen_for_instagram = selector.select_material(materials, history, today=date(2026, 7, 30), platform="instagram")
    assert chosen_for_instagram["id"] in {"room-a", "room-b"}


def test_select_text_required_platforms_excludes_texts_missing_the_checkbox():
    # 本文が長すぎるためXのチェックを外した文言は、Xが必須プラットフォームのときは選ばれない
    texts = [
        make_text("ig-only", platforms={"x": False, "instagram": True, "facebook": True, "google": True}),
        make_text("x-ok", platforms={"x": True, "instagram": True, "facebook": True, "google": True}),
    ]
    for _ in range(20):
        chosen = selector.select_text(texts, history=[], required_platforms=["x"])
        assert chosen["id"] == "x-ok"


def test_select_text_required_platforms_raises_when_none_match():
    texts = [make_text("ig-only", platforms={"x": False, "instagram": True, "facebook": True, "google": True})]
    with pytest.raises(selector.NoEligibleTextError):
        selector.select_text(texts, history=[], required_platforms=["x"])


def test_select_text_without_required_platforms_ignores_the_filter():
    texts = [make_text("ig-only", platforms={"x": False, "instagram": True, "facebook": True, "google": True})]
    chosen = selector.select_text(texts, history=[])
    assert chosen["id"] == "ig-only"


def test_select_platform_pair_applies_its_own_required_platform():
    materials = [make_material("a", ["通年"])]
    texts = [
        make_text("ig-only", platforms={"x": False, "instagram": True, "facebook": True, "google": True}),
        make_text("x-ok", platforms={"x": True, "instagram": True, "facebook": True, "google": True}),
    ]
    for _ in range(20):
        result = selector.select_platform_pair(materials, texts, history=[], platform="x", today=date(2026, 7, 30))
        assert result.text["id"] == "x-ok"
