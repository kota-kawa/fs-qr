"""Task ルームとカードの生 SQL データ層。"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text

from cache_utils import cache_data, invalidate_cache_prefix
from database import db_session, execute_query
from password_security import hash_password, verify_password


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
    return item


async def list_items(room_id: str) -> list[dict[str, Any]]:
    rows = await execute_query(
        """
        SELECT item_id, title, note, board_status, priority, category, start_date, due_date, position, version, created_at, updated_at
        FROM task_item WHERE room_id = :room_id ORDER BY FIELD(board_status, 'todo', 'doing', 'done'), position, item_id
    """,
        {"room_id": room_id},
        fetch=True,
    )
    return [_serialize_item(row) for row in rows]


async def list_categories(room_id: str) -> list[str]:
    rows = await execute_query(
        """
        SELECT DISTINCT category FROM task_item WHERE room_id = :room_id
        AND category IS NOT NULL AND category <> '' ORDER BY category
    """,
        {"room_id": room_id},
        fetch=True,
    )
    return [str(row["category"]) for row in rows]


async def count_items(room_id: str) -> int:
    rows = await execute_query(
        "SELECT COUNT(*) AS count FROM task_item WHERE room_id = :room_id",
        {"room_id": room_id},
        fetch=True,
    )
    return int(rows[0]["count"]) if rows else 0


async def create_item(room_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
    status = values["board_status"]
    async with db_session.begin():
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
            INSERT INTO task_item (room_id, title, note, board_status, priority, category, start_date, due_date, position, created_at, updated_at)
            VALUES (:room_id, :title, :note, :board_status, :priority, :category, :start_date, :due_date, :position, NOW(6), NOW(6))
        """),
            {
                **values,
                "room_id": room_id,
                "category": values.get("category") or None,
                "start_date": values.get("start_date") or None,
                "due_date": values.get("due_date") or None,
                "position": position,
            },
        )
        item_id = result.lastrowid
    return await get_item(room_id, int(item_id))


async def get_item(room_id: str, item_id: int) -> dict[str, Any] | None:
    rows = await execute_query(
        """
        SELECT item_id, title, note, board_status, priority, category, start_date, due_date, position, version, created_at, updated_at
        FROM task_item WHERE room_id = :room_id AND item_id = :item_id
    """,
        {"room_id": room_id, "item_id": item_id},
        fetch=True,
    )
    return _serialize_item(rows[0]) if rows else None


async def update_item(
    room_id: str, item_id: int, values: dict[str, Any], version: int
) -> tuple[dict[str, Any] | None, bool]:
    allowed = {
        "title",
        "note",
        "board_status",
        "priority",
        "category",
        "start_date",
        "due_date",
        "position",
    }
    fields = {key: value for key, value in values.items() if key in allowed}
    if not fields:
        return await get_item(room_id, item_id), True
    if "category" in fields:
        fields["category"] = fields["category"] or None
    if "start_date" in fields:
        fields["start_date"] = fields["start_date"] or None
    if "due_date" in fields:
        fields["due_date"] = fields["due_date"] or None
    # フィールド名を組み立てず、存在フラグで更新対象を制御する。
    params = {"room_id": room_id, "item_id": item_id, "version": version}
    for key in allowed:
        params[f"has_{key}"] = key in fields
        params[key] = fields.get(key)
    result = await execute_query(
        text("""
        UPDATE task_item SET
          title = CASE WHEN :has_title THEN :title ELSE title END,
          note = CASE WHEN :has_note THEN :note ELSE note END,
          board_status = CASE WHEN :has_board_status THEN :board_status ELSE board_status END,
          priority = CASE WHEN :has_priority THEN :priority ELSE priority END,
          category = CASE WHEN :has_category THEN :category ELSE category END,
          start_date = CASE WHEN :has_start_date THEN :start_date ELSE start_date END,
          due_date = CASE WHEN :has_due_date THEN :due_date ELSE due_date END,
          position = CASE WHEN :has_position THEN :position ELSE position END,
          version = version + 1, updated_at = NOW(6)
        WHERE room_id = :room_id AND item_id = :item_id AND version = :version
        """),
        params,
    )
    if result != 1:
        return await get_item(room_id, item_id), False
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
