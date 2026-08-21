"""Task ルームとカードの生 SQL データ層。"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text

from cache_utils import cache_data, invalidate_cache_prefix
from database import db_session, execute_query
from password_security import hash_password, verify_password


class InvalidTaskDateRange(ValueError):
    """タスクの開始日が期限日より後になったことを示す。"""


class TaskItemLimitReached(ValueError):
    """ルーム内のタスク上限に達したことを示す。"""


class TaskTagLimitReached(ValueError):
    """ルーム内のタグ上限に達したことを示す。"""


def validate_task_date_range(start_date: Any, due_date: Any) -> None:
    """開始日と期限日の前後関係を DB 更新直前にも検証する。

    API の部分更新では片方の値しか届かないため、Pydantic の入力検証だけでは
    既存値との組み合わせを確認できない。ここでは文字列・date のどちらも受け、
    トランザクション内で合成した最終値を検証する。
    """
    start = start_date.isoformat() if hasattr(start_date, "isoformat") else start_date
    due = due_date.isoformat() if hasattr(due_date, "isoformat") else due_date
    if start and due and str(start) > str(due):
        raise InvalidTaskDateRange("開始日は期限日以前の日付を指定してください。")


async def create_room(
    id_: str, password: str, room_id: str, retention_hours: int = 24
) -> None:
    await execute_query(
        text("""
        INSERT INTO task_room (time, id, password, room_id, retention_days, retention_hours, expires_at, status)
        VALUES (NOW(), :id, :password, :room_id, 1, :retention_hours,
                DATE_ADD(NOW(), INTERVAL :retention_hours HOUR), 'active')
    """),
        {
            "id": id_,
            "password": hash_password(password),
            "room_id": room_id,
            "retention_hours": retention_hours,
        },
    )
    await invalidate_cache_prefix(get_room_meta)
    await invalidate_cache_prefix(pick_room_id)


async def get_room_meta_direct(
    room_id: str, password: str | None = None
) -> dict[str, Any] | None:
    rows = await execute_query(
        """
        SELECT room_id, id, password, time, retention_hours, expires_at, status, deleted_at
        FROM task_room WHERE room_id = :room_id AND status = 'active' AND expires_at > NOW()
    """,
        {"room_id": room_id},
        fetch=True,
    )
    if not rows:
        return None
    row = dict(rows[0])
    if password is not None and not verify_password(row.get("password"), password):
        return None
    return row


@cache_data(ttl=60, strip_keys=("password",))
async def get_room_meta(room_id: str, password: str | None = None):
    return await get_room_meta_direct(room_id, password)


async def pick_room_id_direct(id_: str, password: str) -> str | None:
    rows = await execute_query(
        "SELECT room_id, password FROM task_room WHERE id = :id",
        {"id": id_},
        fetch=True,
    )
    for row in rows:
        if verify_password(row.get("password"), password):
            return row["room_id"]
    return None


@cache_data(ttl=60)
async def pick_room_id(id_: str, password: str) -> str | None:
    return await pick_room_id_direct(id_, password)


# タスクの列は複数箇所で参照するため、1か所にまとめて定義のずれを防ぐ。
# The item column list is shared so the SELECTs cannot drift apart.
_ITEM_COLUMNS = (
    "item_id, title, note, board_status, priority, "
    "start_date, due_date, position, version, created_at, updated_at"
)


def _serialize_item(row: Any) -> dict[str, Any]:
    item = dict(row)
    for key in ("created_at", "updated_at"):
        value = item.get(key)
        if value is not None and hasattr(value, "isoformat"):
            item[key] = value.isoformat(sep=" ", timespec="microseconds")
    start = item.get("start_date")
    if start is not None and hasattr(start, "isoformat"):
        item["start_date"] = start.isoformat()
    due = item.get("due_date")
    if due is not None and hasattr(due, "isoformat"):
        item["due_date"] = due.isoformat()
    item.setdefault("tags", [])
    return item


def _named_params(prefix: str, values: list[int]) -> tuple[str, dict[str, Any]]:
    """IN 句用のプレースホルダを生成する。値は必ずバインドパラメータで渡す。

    Builds ``:prefix_0, :prefix_1`` placeholders so IN clauses stay parameterized.
    """
    names = [f"{prefix}_{index}" for index in range(len(values))]
    placeholders = ", ".join(f":{name}" for name in names)
    return placeholders, dict(zip(names, values))


def _serialize_tag(row: Any) -> dict[str, Any]:
    tag = dict(row)
    return {"tag_id": int(tag["tag_id"]), "name": str(tag["name"])}


async def list_tags(room_id: str) -> list[dict[str, Any]]:
    """ルームのタグ一覧を、利用中のタスク数付きで返す。"""
    rows = await execute_query(
        """
        SELECT t.tag_id, t.name, COUNT(it.item_id) AS item_count
        FROM task_tag t
        LEFT JOIN task_item_tag it ON it.tag_id = t.tag_id
        WHERE t.room_id = :room_id
        GROUP BY t.tag_id, t.name
        ORDER BY t.name
    """,
        {"room_id": room_id},
        fetch=True,
    )
    return [
        dict(_serialize_tag(row), item_count=int(dict(row).get("item_count") or 0))
        for row in (rows or [])
    ]


async def _load_item_tags(room_id: str, item_ids: list[int]) -> dict[int, list[dict]]:
    """タスク ID ごとのタグ一覧をまとめて取得する（N+1 クエリを避ける）。"""
    if not item_ids:
        return {}
    placeholders, params = _named_params("item", item_ids)
    params["room_id"] = room_id
    rows = await execute_query(
        # 差し込むのは _named_params が生成したプレースホルダ名だけで、値はバインドで渡す。
        # Only generated placeholder names are interpolated; values stay bound.
        f"""
        SELECT it.item_id, t.tag_id, t.name
        FROM task_item_tag it
        JOIN task_tag t ON t.tag_id = it.tag_id
        WHERE t.room_id = :room_id AND it.item_id IN ({placeholders})
        ORDER BY t.name
    """,  # noqa: S608
        params,
        fetch=True,
    )
    tags_by_item: dict[int, list[dict]] = {}
    for row in rows or []:
        mapping = dict(row)
        tags_by_item.setdefault(int(mapping["item_id"]), []).append(
            _serialize_tag(mapping)
        )
    return tags_by_item


async def _attach_tags(
    room_id: str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    tags_by_item = await _load_item_tags(
        room_id, [int(item["item_id"]) for item in items]
    )
    for item in items:
        item["tags"] = tags_by_item.get(int(item["item_id"]), [])
    return items


async def create_tag(
    room_id: str, name: str, max_tags: int | None = None
) -> dict[str, Any]:
    """タグを追加する。同名タグがあれば既存のタグをそのまま返す。"""
    async with db_session.begin():
        result = await db_session.execute(
            text("""
            SELECT tag_id, name FROM task_tag WHERE room_id = :room_id AND name = :name
        """),
            {"room_id": room_id, "name": name},
        )
        existing = result.mappings().first()
        if existing:
            return _serialize_tag(existing)

        if max_tags is not None:
            # ルーム行をロックして同時追加でも上限を超えないようにする。
            # Lock the room row so concurrent creates cannot exceed the limit.
            await db_session.execute(
                text(
                    "SELECT room_id FROM task_room WHERE room_id = :room_id FOR UPDATE"
                ),
                {"room_id": room_id},
            )
            result = await db_session.execute(
                text("SELECT COUNT(*) AS count FROM task_tag WHERE room_id = :room_id"),
                {"room_id": room_id},
            )
            count_row = result.mappings().first()
            if count_row and int(count_row["count"]) >= max_tags:
                raise TaskTagLimitReached

        result = await db_session.execute(
            text("""
            INSERT INTO task_tag (room_id, name, created_at) VALUES (:room_id, :name, NOW(6))
        """),
            {"room_id": room_id, "name": name},
        )
        tag_id = int(result.lastrowid)
    return {"tag_id": tag_id, "name": name}


async def rename_tag(room_id: str, tag_id: int, name: str) -> dict[str, Any] | None:
    """タグ名を変更する。同名タグが既にある場合は None を返す。"""
    rows = await execute_query(
        "SELECT tag_id FROM task_tag WHERE room_id = :room_id AND name = :name AND tag_id <> :tag_id",
        {"room_id": room_id, "name": name, "tag_id": tag_id},
        fetch=True,
    )
    if rows:
        return None
    updated = await execute_query(
        "UPDATE task_tag SET name = :name WHERE room_id = :room_id AND tag_id = :tag_id",
        {"name": name, "room_id": room_id, "tag_id": tag_id},
    )
    if not updated:
        return None
    return {"tag_id": int(tag_id), "name": name}


async def delete_tag(room_id: str, tag_id: int) -> bool:
    """タグを削除する。タスク側の紐づけは外部キーの ON DELETE CASCADE で消える。"""
    result = await execute_query(
        "DELETE FROM task_tag WHERE room_id = :room_id AND tag_id = :tag_id",
        {"room_id": room_id, "tag_id": tag_id},
    )
    return bool(result)


async def resolve_tag_names(
    room_id: str, names: list[str], max_tags: int | None = None
) -> list[int]:
    """タグ名の一覧を ID へ解決する。存在しない名前は新規作成する。

    インポートなど、名前でタグを受け取る経路で使う。上限に達した場合は
    そこまでに解決できた ID だけを返し、残りは黙って捨てる。
    """
    tag_ids: list[int] = []
    for name in names:
        try:
            tag = await create_tag(room_id, name, max_tags=max_tags)
        except TaskTagLimitReached:
            break
        tag_ids.append(int(tag["tag_id"]))
    return tag_ids


async def _replace_item_tags(room_id: str, item_id: int, tag_ids: list[int]) -> None:
    """タスクのタグ紐づけを指定内容で置き換える。呼び出し側の transaction 内で使う。

    他ルームのタグ ID を渡されても task_tag 側の room_id で弾かれるため、
    ルームをまたいだ紐づけは発生しない。
    """
    await db_session.execute(
        text("DELETE FROM task_item_tag WHERE item_id = :item_id"),
        {"item_id": item_id},
    )
    if not tag_ids:
        return
    placeholders, params = _named_params("tag", tag_ids)
    params.update({"item_id": item_id, "room_id": room_id})
    await db_session.execute(
        # 同上：プレースホルダ名のみを差し込み、タグ ID はバインドで渡す。
        # Same as above: only placeholder names are interpolated.
        text(f"""
        INSERT INTO task_item_tag (item_id, tag_id)
        SELECT :item_id, tag_id FROM task_tag
        WHERE room_id = :room_id AND tag_id IN ({placeholders})
    """),  # noqa: S608
        params,
    )


async def list_items(room_id: str) -> list[dict[str, Any]]:
    rows = await execute_query(
        # 差し込むのは定数の列一覧のみ。 / Only the constant column list is interpolated.
        f"""
        SELECT {_ITEM_COLUMNS}
        FROM task_item WHERE room_id = :room_id ORDER BY FIELD(board_status, 'todo', 'doing', 'done'), position, item_id
    """,  # noqa: S608
        {"room_id": room_id},
        fetch=True,
    )
    return await _attach_tags(room_id, [_serialize_item(row) for row in (rows or [])])


async def count_items(room_id: str) -> int:
    rows = await execute_query(
        "SELECT COUNT(*) AS count FROM task_item WHERE room_id = :room_id",
        {"room_id": room_id},
        fetch=True,
    )
    return int(rows[0]["count"]) if rows else 0


async def create_item(
    room_id: str, values: dict[str, Any], max_items: int | None = None
) -> dict[str, Any] | None:
    status = values["board_status"]
    validate_task_date_range(values.get("start_date"), values.get("due_date"))
    async with db_session.begin():
        if max_items is not None:
            # Serialize concurrent creates per room so the application limit is
            # enforced atomically. ルーム行をロックして同時追加の上限超過を防ぐ。
            await db_session.execute(
                text("""
                SELECT room_id FROM task_room WHERE room_id = :room_id FOR UPDATE
            """),
                {"room_id": room_id},
            )
            result = await db_session.execute(
                text("""
                SELECT COUNT(*) AS count FROM task_item WHERE room_id = :room_id
            """),
                {"room_id": room_id},
            )
            count_row = result.mappings().first()
            if count_row and int(count_row["count"]) >= max_items:
                raise TaskItemLimitReached

        result = await db_session.execute(
            text("""
            SELECT COALESCE(MAX(position), 0) AS last_position FROM task_item
            WHERE room_id = :room_id AND board_status = :board_status FOR UPDATE
        """),
            {"room_id": room_id, "board_status": status},
        )
        position = int(result.mappings().first()["last_position"]) + 100
        result = await db_session.execute(
            text("""
            INSERT INTO task_item (room_id, title, note, board_status, priority, start_date, due_date, position, created_at, updated_at)
            VALUES (:room_id, :title, :note, :board_status, :priority, :start_date, :due_date, :position, NOW(6), NOW(6))
        """),
            {
                "room_id": room_id,
                "title": values["title"],
                "note": values.get("note") or "",
                "board_status": status,
                "priority": values.get("priority") or "normal",
                "start_date": values.get("start_date") or None,
                "due_date": values.get("due_date") or None,
                "position": position,
            },
        )
        item_id = int(result.lastrowid)
        # タグの紐づけも同じ transaction で確定させ、タグだけ欠けた状態を作らない。
        # Link tags in the same transaction so an item never lands without them.
        await _replace_item_tags(room_id, item_id, list(values.get("tag_ids") or []))
    return await get_item(room_id, item_id)


async def get_item(room_id: str, item_id: int) -> dict[str, Any] | None:
    rows = await execute_query(
        # 差し込むのは定数の列一覧のみ。 / Only the constant column list is interpolated.
        f"""
        SELECT {_ITEM_COLUMNS}
        FROM task_item WHERE room_id = :room_id AND item_id = :item_id
    """,  # noqa: S608
        {"room_id": room_id, "item_id": item_id},
        fetch=True,
    )
    if not rows:
        return None
    items = await _attach_tags(room_id, [_serialize_item(rows[0])])
    return items[0]


async def update_item(
    room_id: str, item_id: int, values: dict[str, Any], version: int
) -> tuple[dict[str, Any] | None, bool]:
    allowed = {
        "title",
        "note",
        "board_status",
        "priority",
        "start_date",
        "due_date",
        "position",
    }
    fields = {key: value for key, value in values.items() if key in allowed}
    # tag_ids が指定されたときはタグを丸ごと置き換える（空配列＝全解除）。
    # A present tag_ids replaces the whole set; an empty list clears the tags.
    tag_ids = values.get("tag_ids")
    has_tag_update = tag_ids is not None
    if not fields and not has_tag_update:
        return await get_item(room_id, item_id), True
    if "start_date" in fields:
        fields["start_date"] = fields["start_date"] or None
    if "due_date" in fields:
        fields["due_date"] = fields["due_date"] or None

    # 競合時に返す現在値。タグの付与は transaction の外で行う（execute_query が
    # 自前で commit / rollback するため、begin() の中からは呼べない）。
    # Holds the current row on a version conflict; tags are attached after the
    # transaction because execute_query commits on its own.
    conflict: dict[str, Any] | None = None

    # Lock the current row so a partial date update is checked against the same
    # values that the UPDATE will modify. 部分更新でも既存値との組み合わせを
    # 同じトランザクション内で検証し、開始日と期限日の逆転を防ぐ。
    async with db_session.begin():
        result = await db_session.execute(
            # 差し込むのは定数の列一覧のみ。 / Only the constant column list is interpolated.
            text(f"""
            SELECT {_ITEM_COLUMNS}
            FROM task_item
            WHERE room_id = :room_id AND item_id = :item_id
            FOR UPDATE
        """),  # noqa: S608
            {"room_id": room_id, "item_id": item_id},
        )
        current_row = result.mappings().first()
        if current_row is None:
            return None, False
        current = _serialize_item(current_row)
        if int(current["version"]) != version:
            conflict = current
        else:
            validate_task_date_range(
                fields.get("start_date", current.get("start_date")),
                fields.get("due_date", current.get("due_date")),
            )

            # フィールド名を組み立てず、存在フラグで更新対象を制御する。
            params = {"room_id": room_id, "item_id": item_id, "version": version}
            for key in allowed:
                params[f"has_{key}"] = key in fields
                params[key] = fields.get(key)
            await db_session.execute(
                text("""
                UPDATE task_item SET
                  title = CASE WHEN :has_title THEN :title ELSE title END,
                  note = CASE WHEN :has_note THEN :note ELSE note END,
                  board_status = CASE WHEN :has_board_status THEN :board_status ELSE board_status END,
                  priority = CASE WHEN :has_priority THEN :priority ELSE priority END,
                  start_date = CASE WHEN :has_start_date THEN :start_date ELSE start_date END,
                  due_date = CASE WHEN :has_due_date THEN :due_date ELSE due_date END,
                  position = CASE WHEN :has_position THEN :position ELSE position END,
                  version = version + 1, updated_at = NOW(6)
                WHERE room_id = :room_id AND item_id = :item_id AND version = :version
                """),
                params,
            )
            if has_tag_update:
                await _replace_item_tags(room_id, item_id, list(tag_ids or []))

    if conflict is not None:
        # 競合時も最新のタグを添えて返し、画面のタグ表示が消えないようにする。
        # The conflict response carries tags too, so the UI keeps showing them.
        return (await _attach_tags(room_id, [conflict]))[0], False
    return await get_item(room_id, item_id), True


async def delete_item(room_id: str, item_id: int) -> bool:
    result = await execute_query(
        "DELETE FROM task_item WHERE room_id = :room_id AND item_id = :item_id",
        {"room_id": room_id, "item_id": item_id},
    )
    return bool(result)


async def reorder_items(
    room_id: str, board_status: str, item_ids: list[int]
) -> list[dict[str, Any]] | None:
    if len(item_ids) != len(set(item_ids)):
        return None
    async with db_session.begin():
        result = await db_session.execute(
            text("""
            SELECT item_id FROM task_item WHERE room_id = :room_id AND board_status = :board_status FOR UPDATE
        """),
            {"room_id": room_id, "board_status": board_status},
        )
        existing = {int(row["item_id"]) for row in result.mappings()}
        if existing != set(item_ids):
            return None
        for index, item_id in enumerate(item_ids, start=1):
            await db_session.execute(
                text("""
                UPDATE task_item SET position = :position, updated_at = NOW(6), version = version + 1
                WHERE room_id = :room_id AND item_id = :item_id
            """),
                {"position": index * 100, "room_id": room_id, "item_id": item_id},
            )
    return [
        item
        for item in await list_items(room_id)
        if item["board_status"] == board_status
    ]


async def remove_room(room_id: str, status: str = "deleted") -> None:
    await execute_query(
        "UPDATE task_room SET status = :status, deleted_at = NOW() WHERE room_id = :room_id",
        {"status": status, "room_id": room_id},
    )
    try:
        from share_links import ServiceKey, revoke_resource_links

        await revoke_resource_links(service_key=ServiceKey.TASK, resource_id=room_id)
    finally:
        await invalidate_cache_prefix(get_room_meta)
        await invalidate_cache_prefix(pick_room_id)


async def remove_expired_rooms() -> list[str]:
    rows = await execute_query(
        "SELECT room_id FROM task_room WHERE status = 'active' AND expires_at <= NOW()",
        fetch=True,
    )
    room_ids = [str(row["room_id"]) for row in rows]
    await asyncio.gather(*(remove_room(room_id, "expired") for room_id in room_ids))
    return room_ids
