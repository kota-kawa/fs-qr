"""ルーム CRUD で共有する安全な SQL とキャッシュ識別子。

Group / Note / Task はテーブル名や status 列の有無が異なりますが、有効期限を
含む取得条件と期限切れ一覧の SQL は同じです。テーブル名はコードで固定し、値は
必ずバインドパラメータにすることで、共通化後も SQL インジェクションの余地を
増やしません。

The repository is intentionally small: service data modules keep transactions and
password verification, while this module owns the repeated active/expired predicates.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Awaitable, Callable, Sequence

from sqlalchemy import text

from password_security import verify_password


@dataclass(frozen=True)
class RoomTable:
    name: str
    id_column: str = "room_id"
    status_column: str | None = None
    expiry_column: str = "expires_at"

    @property
    def active_predicate(self) -> str:
        parts = []
        if self.status_column:
            parts.append(f"{self.status_column} = 'active'")
        parts.append(f"{self.expiry_column} > NOW()")
        return " AND ".join(parts)

    @property
    def expired_predicate(self) -> str:
        status = f"{self.status_column} = 'active' AND " if self.status_column else ""
        return f"{status}{self.expiry_column} <= NOW()"

    def active_select(self, columns: str = "*") -> Any:
        return text(
            f"SELECT {columns} FROM {self.name} "  # noqa: S608 - table and columns are fixed by RoomTable callers
            f"WHERE {self.id_column} = :room_id AND {self.active_predicate}"
        )

    def expired_ids_select(self) -> Any:
        return text(
            f"SELECT {self.id_column} FROM {self.name} WHERE {self.expired_predicate}"  # noqa: S608 - table and columns are fixed RoomTable constants
        )


GROUP_ROOMS = RoomTable("room", status_column="status")
NOTE_ROOMS = RoomTable("note_room", status_column="status")
TASK_ROOMS = RoomTable("task_room", status_column="status")


async def revoke_room_links(
    service_key: Any,
    resource_id: str,
    *,
    logger: logging.Logger | None = None,
) -> bool:
    """共有リンクの取り消しを共通化し、データ層の import cycle を避ける。

    The import stays lazy for compatibility with the historical
    ``share_links`` ↔ data-layer dependency. Link revocation is a cleanup
    side effect, so callers can inspect the boolean while the database result
    remains authoritative.
    """

    try:
        from share_links import revoke_resource_links

        await revoke_resource_links(service_key=service_key, resource_id=resource_id)
    except Exception:
        if logger is not None:
            logger.warning(
                "Failed to revoke room share links: service=%s resource_id=%s",
                service_key,
                resource_id,
                exc_info=True,
            )
        return False
    return True


async def find_room_id_by_credentials(
    execute: Callable[..., Awaitable[Sequence[Any]]],
    table: RoomTable,
    public_id: str,
    password: str,
) -> str | None:
    """Find an active room by its public ID and verify its password.

    Group, Note and Task intentionally keep their historical ``id`` lookup
    semantics.  Only the table name varies, so the query and constant-time
    password verification live here while each data module retains its cache
    decorator and compatibility aliases.
    """

    rows = await execute(
        text(  # noqa: S608 - table is one of the fixed RoomTable constants
            f"SELECT room_id, password FROM {table.name} "  # noqa: S608
            f"WHERE id = :id AND {table.active_predicate}"  # noqa: S608
        ),
        {"id": public_id},
        fetch=True,
    )
    for row in rows:
        mapping = getattr(row, "_mapping", row)
        if verify_password(mapping.get("password"), password):
            return mapping.get(table.id_column)
    return None


async def room_id_exists(
    execute: Callable[..., Awaitable[Sequence[Any]]],
    table: RoomTable,
    room_id: str,
) -> bool:
    """Return whether an ID is reserved, including a soft-deleted room.

    A deleted Group room remains as a tombstone so a browser session containing
    the old room ID can never become authorized for a later room with that ID.
    ID allocation must therefore check all rows, not only active rooms.
    """

    rows = await execute(
        text(  # noqa: S608 - table is one of the fixed RoomTable constants
            f"SELECT 1 FROM {table.name} WHERE {table.id_column} = :room_id LIMIT 1"  # noqa: S608
        ),
        {"room_id": room_id},
        fetch=True,
    )
    return bool(rows)


async def get_active_room(
    execute: Callable[..., Awaitable[Sequence[Any]]],
    table: RoomTable,
    room_id: str,
    *,
    columns: str = "*",
) -> Any | None:
    """指定サービスの有効なルームを 1 件取得する。"""

    rows = await execute(table.active_select(columns), {"room_id": room_id}, fetch=True)
    return rows[0] if rows else None


async def list_expired_room_ids(
    execute: Callable[..., Awaitable[Sequence[Any]]], table: RoomTable
) -> list[str]:
    """期限切れ掃除対象の ID を共通条件で取得する。"""

    rows = await execute(table.expired_ids_select(), fetch=True)
    room_ids: list[str] = []
    for row in rows:
        mapping = getattr(row, "_mapping", row)
        room_id = mapping.get(table.id_column)
        if room_id:
            room_ids.append(str(room_id))
    return room_ids


__all__ = [
    "GROUP_ROOMS",
    "NOTE_ROOMS",
    "TASK_ROOMS",
    "RoomTable",
    "get_active_room",
    "find_room_id_by_credentials",
    "room_id_exists",
    "list_expired_room_ids",
    "revoke_room_links",
]
