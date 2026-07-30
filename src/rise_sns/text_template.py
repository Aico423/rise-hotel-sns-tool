"""投稿文言の中に書かれたプレースホルダーを、実際の部屋の情報に置き換える。

スタッフが投稿文言を登録するたびに「最大○名様」「ベッドサイズ○○」等を手入力すると、
実際の部屋の仕様と食い違う投稿になりかねない（例: 8人部屋の写真なのに2人部屋の文言）。
そのため、部屋タイプごとの仕様は config.json の room_types に一元管理しておき、
文言側は {max_guests} のようなプレースホルダーだけを書けば、その日選ばれた客室写真の
部屋タイプ・部屋番号から自動的に実際の値が差し込まれるようにする。
"""
from __future__ import annotations

PLACEHOLDERS = ("room_type", "room_number", "bed_size", "max_guests")


def room_types_by_name(config_data: dict) -> dict[str, dict]:
    return {rt["name"]: rt for rt in config_data.get("room_types", []) if rt.get("name")}


def render_text(text: str, material: dict, room_type_defs: dict[str, dict]) -> str:
    """textの中の {room_type} {room_number} {bed_size} {max_guests} を実際の値に置き換える。

    対応する部屋タイプ定義が無い場合や値が空の場合は、プレースホルダーを空文字に置き換える
    （読めない文字列がそのまま投稿されてしまうことを避けるため）。
    """
    room_type_name = material.get("room_type", "") or ""
    room_type_def = room_type_defs.get(room_type_name, {})

    values = {
        "room_type": room_type_name,
        "room_number": material.get("room_number", "") or "",
        "bed_size": room_type_def.get("bed_size", "") or "",
        "max_guests": str(room_type_def.get("max_guests", "")) if room_type_def.get("max_guests") is not None else "",
    }

    rendered = text
    for key in PLACEHOLDERS:
        rendered = rendered.replace("{" + key + "}", values.get(key, ""))
    return rendered
