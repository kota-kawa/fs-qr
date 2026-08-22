"""Task の API ルート共通の認可チェック。

items / tags など複数のルーターから使うため、1か所へ切り出している。
Shared by the item and tag routers so the access rules cannot drift apart.
"""

from __future__ import annotations

from fastapi import Request

from web import enforce_csrf
from . import task_data
from .task_access import has_task_room_access
from .task_responses import task_api_error


async def authorize_task_room(request: Request, room_id: str, *, csrf: bool = False):
    """アクセス権とルームの生存を確認し、拒否する場合はエラー応答を返す。"""
    if csrf:
        await enforce_csrf(request)
    if not has_task_room_access(request, room_id):
        return task_api_error(
            "task.room_access_denied",
            "このルームへのアクセス権がありません。",
            status_code=404,
        )
    if not await task_data.get_room_meta_direct(room_id):
        return task_api_error(
            "task.room_expired",
            "ルームの有効期限が切れているか、削除されています。",
            status_code=404,
        )
    return None
