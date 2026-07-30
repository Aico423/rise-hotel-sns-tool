from PIL import Image

from rise_sns import decorations


def make_decoration(id_, tags, placement, active=True):
    return {"id": id_, "image_path": f"decorations/{id_}.png", "tags": tags, "placement": placement, "active": active}


def test_select_decorations_matches_by_tag_overlap():
    decos = [make_decoration("book-now", ["予約訴求"], "bottom_right")]
    chosen = decorations.select_decorations(decos, creative_tags={"予約訴求", "夏"})
    assert [d["id"] for d in chosen] == ["book-now"]


def test_select_decorations_skips_zone_with_no_match():
    decos = [make_decoration("tokyo", ["東京"], "bottom_center")]
    chosen = decorations.select_decorations(decos, creative_tags={"夏", "和室"})
    assert chosen == []


def test_select_decorations_ignores_inactive():
    decos = [make_decoration("book-now", ["予約訴求"], "bottom_right", active=False)]
    chosen = decorations.select_decorations(decos, creative_tags={"予約訴求"})
    assert chosen == []


def test_select_decorations_one_per_placement_zone():
    decos = [
        make_decoration("a", ["夏"], "bottom_right"),
        make_decoration("b", ["夏"], "bottom_right"),
    ]
    chosen = decorations.select_decorations(decos, creative_tags={"夏"})
    assert len(chosen) == 1
    assert chosen[0]["id"] in ("a", "b")


def test_select_decorations_multiple_zones_independent():
    decos = [
        make_decoration("book-now", ["予約訴求"], "bottom_right"),
        make_decoration("tokyo", ["東京"], "bottom_center"),
    ]
    chosen = decorations.select_decorations(decos, creative_tags={"予約訴求", "東京"})
    ids = {d["id"] for d in chosen}
    assert ids == {"book-now", "tokyo"}


def test_resize_stamp_scales_down_large_stamp():
    stamp = Image.new("RGBA", (2000, 1000), (255, 0, 0, 255))
    resized = decorations._resize_stamp(stamp, base_size=(1080, 1920))
    # 短辺1080の24% = 259.2 -> 259が上限
    assert max(resized.size) <= 260
    original_ratio = stamp.width / stamp.height
    resized_ratio = resized.width / resized.height
    assert abs(resized_ratio - original_ratio) < 0.02


def test_resize_stamp_leaves_small_stamp_unchanged():
    stamp = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
    resized = decorations._resize_stamp(stamp, base_size=(1080, 1920))
    assert resized.size == (50, 50)


def test_position_for_each_placement():
    base_size = (1000, 2000)
    stamp_size = (100, 100)
    padding = 40

    assert decorations._position_for("top_left", base_size, stamp_size, padding) == (40, 40)
    assert decorations._position_for("top_right", base_size, stamp_size, padding) == (860, 40)
    assert decorations._position_for("top_center", base_size, stamp_size, padding) == (450, 40)
    assert decorations._position_for("bottom_left", base_size, stamp_size, padding) == (40, 1860)
    assert decorations._position_for("bottom_right", base_size, stamp_size, padding) == (860, 1860)
    assert decorations._position_for("bottom_center", base_size, stamp_size, padding) == (450, 1860)


def test_apply_decorations_composites_stamp_onto_image():
    base = Image.new("RGB", (400, 400), color=(10, 10, 10))
    stamp_img = Image.new("RGBA", (80, 80), color=(255, 0, 0, 255))
    deco = make_decoration("book-now", ["予約訴求"], "bottom_right")

    result = decorations.apply_decorations(base, [deco], open_stamp=lambda d: stamp_img)

    assert result.size == (400, 400)
    assert result.mode == "RGB"
    # 右下付近のピクセルはスタンプの赤色になっているはず
    padding = int(min(base.size) * decorations.PADDING_RATIO)
    x = 400 - padding - 10
    y = 400 - padding - 10
    assert result.getpixel((x, y)) == (255, 0, 0)


def test_apply_decorations_noop_when_no_decorations():
    base = Image.new("RGB", (200, 200), color=(1, 2, 3))
    result = decorations.apply_decorations(base, [], open_stamp=lambda d: d)
    assert result.size == (200, 200)
    assert result.getpixel((100, 100)) == (1, 2, 3)
