"""所有者ルーム削除の共通フロー。

レート制限や CSRF は各ルートの前段で行い、ここでは「有効なルームの確認 →
所有者権限 → データ層削除 → セッションの忘却」というサービス共通の骨格を
扱います。サービス固有の realtime 通知やファイル削除結果はコールバックへ
委譲します。

The helper deliberately returns an outcome instead of an HTTP response so callers
can preserve each service's localized JSON/HTML response contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import Request


@dataclass(frozen=True)
class RoomDeleteOutcome:
    status: str
    record: Any = None


async def delete_owned_room(
    request: Request,
    room_id: str,
    *,
    get_active: Callable[[str], Awaitable[Any]],
    can_delete: Callable[[Request, str, Any], bool],
    remove: Callable[[str], Awaitable[Any]],
    forget: Callable[[Request, str], None],
) -> RoomDeleteOutcome:
    """所有者ルームを削除し、結果を共通の状態名で返す。"""

    record = await get_active(room_id)
    if not record:
        return RoomDeleteOutcome("not_found")
    if not can_delete(request, room_id, record):
        return RoomDeleteOutcome("forbidden", record)

    removed = await remove(room_id)
    if removed is False:
        return RoomDeleteOutcome("failed", record)
    forget(request, room_id)
    return RoomDeleteOutcome("deleted", record)


__all__ = ["RoomDeleteOutcome", "delete_owned_room"]
