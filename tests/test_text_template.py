from rise_sns import text_template


def make_config():
    return {
        "room_types": [
            {"name": "Type A", "bed_size": "上段Wide-Double 155cm×200cm / 下段Semi-Double 140cm×200cm", "max_guests": 10},
            {"name": "Type B", "bed_size": "上段Wide-Double 155cm×200cm / 下段King 185cm×200cm", "max_guests": 8},
        ]
    }


def test_room_types_by_name_indexes_by_name():
    lookup = text_template.room_types_by_name(make_config())
    assert set(lookup.keys()) == {"Type A", "Type B"}
    assert lookup["Type A"]["max_guests"] == 10


def test_render_text_substitutes_all_placeholders():
    lookup = text_template.room_types_by_name(make_config())
    material = {"room_type": "Type B", "room_number": "601"}
    text = "{room_type}（{room_number}号室）は最大{max_guests}名様まで。ベッド: {bed_size}"

    result = text_template.render_text(text, material, lookup)

    assert result == (
        "Type B（601号室）は最大8名様まで。ベッド: 上段Wide-Double 155cm×200cm / 下段King 185cm×200cm"
    )


def test_render_text_leaves_plain_text_unchanged():
    lookup = text_template.room_types_by_name(make_config())
    material = {"room_type": "Type A", "room_number": "502"}
    text = "今週末もご予約受付中です！"
    assert text_template.render_text(text, material, lookup) == text


def test_render_text_handles_unknown_room_type_gracefully():
    lookup = text_template.room_types_by_name(make_config())
    material = {"room_type": "存在しないタイプ", "room_number": "999"}
    text = "最大{max_guests}名様まで（{bed_size}）"
    assert text_template.render_text(text, material, lookup) == "最大名様まで（）"


def test_render_text_handles_missing_material_fields():
    lookup = text_template.room_types_by_name(make_config())
    material = {}
    text = "{room_type}{room_number}{bed_size}{max_guests}"
    assert text_template.render_text(text, material, lookup) == ""


def test_render_story_body_text_omits_room_number_and_max_guests():
    lookup = text_template.room_types_by_name(make_config())
    material = {"room_type": "Type B", "room_number": "601"}
    text = "{room_number} Bigger Bunk bed {bed_size} {max_guests} Kitchen, cutlery, dryer."

    result = text_template.render_story_body_text(text, material, lookup)

    assert "601" not in result
    assert "8" not in result.split("Bigger")[0]  # max_guestsの値(8)が本文に残っていないこと
    assert result == "Bigger Bunk bed 上段Wide-Double 155cm×200cm / 下段King 185cm×200cm Kitchen, cutlery, dryer."


def test_render_story_body_text_keeps_room_type_and_bed_size():
    lookup = text_template.room_types_by_name(make_config())
    material = {"room_type": "Type A", "room_number": "502"}
    text = "{room_type}: {bed_size}"
    assert text_template.render_story_body_text(text, material, lookup) == (
        "Type A: 上段Wide-Double 155cm×200cm / 下段Semi-Double 140cm×200cm"
    )


def test_render_story_body_text_drops_lines_left_empty_after_omitting_placeholders():
    lookup = text_template.room_types_by_name(make_config())
    material = {"room_type": "Type A", "room_number": "502"}
    text = "{room_number}\nKitchen, cutlery, dryer.\n{max_guests}"
    assert text_template.render_story_body_text(text, material, lookup) == "Kitchen, cutlery, dryer."
