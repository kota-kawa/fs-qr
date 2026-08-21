from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import ValidationError

from api_response import api_error_response, api_ok_response
from models import TaskItemInput, TaskItemUpdateInput, TaskReorderInput
from rate_limit import (
    SCOPE_TASK_ITEM_DELETE,
    check_exponential_backoff,
    clear_exponential_backoff,
    get_client_ip,
    register_exponential_backoff_failure,
)
from settings import (
    TASK_MAX_ITEMS_PER_ROOM,
    TASK_MAX_TAGS_PER_ITEM,
    TASK_MAX_TAGS_PER_ROOM,
)
from web import enforce_csrf
from . import task_data
from .task_authorize import authorize_task_room as _authorize


async def _resolve_tag_ids(room_id: str, payload: TaskItemInput) -> list[int]:
    """作成時のタグ指定を ID の一覧へそろえる。

    ``tag_ids`` は既存タグの ID、``tags`` は名前指定（インポートや復元で使う）で、
    名前の側はルームに無ければ作成してから ID を得る。ID と名前の両方が届いた
    場合は合算されるため、1タスクあたりの上限で最後に切り詰める。
    """
    tag_ids = list(payload.tag_ids)
    if payload.tags:
        resolved = await task_data.resolve_tag_names(
            room_id, payload.tags, max_tags=TASK_MAX_TAGS_PER_ROOM
        )
        tag_ids.extend(tag_id for tag_id in resolved if tag_id not in tag_ids)
    return tag_ids[:TASK_MAX_TAGS_PER_ITEM]


def register_task_item_routes(router: APIRouter) -> None:  # noqa: C901
    @router.get("/task/{room_id}/items", name="task.list_items")
    async def list_task_items(request: Request, room_id: str):
        denied = await _authorize(request, room_id)
        if denied:
            return denied
        return api_ok_response(
            {
                "items": await task_data.list_items(room_id),
                "tags": await task_data.list_tags(room_id),
            }
        )

    @router.post("/task/{room_id}/items", name="task.create_item")
    async def create_task_item(request: Request, room_id: str):
        denied = await _authorize(request, room_id, csrf=True)
        if denied:
            return denied
        if await task_data.count_items(room_id) >= TASK_MAX_ITEMS_PER_ROOM:
            return api_error_response("タスク数の上限に達しました。", status_code=400)
        try:
            payload = TaskItemInput.model_validate(await request.json())
        except (ValidationError, ValueError, TypeError):
            return api_error_response("入力内容が不正です。", status_code=400)
        values = payload.model_dump(exclude={"tags"})
        values["tag_ids"] = await _resolve_tag_ids(room_id, payload)
        try:
            item = await task_data.create_item(
                room_id, values, max_items=TASK_MAX_ITEMS_PER_ROOM
            )
        except task_data.TaskItemLimitReached:
            return api_error_response("タスク数の上限に達しました。", status_code=400)
        return api_ok_response({"item": item}, status_code=201)

    @router.patch("/task/{room_id}/items/{item_id}", name="task.update_item")
    async def update_task_item(request: Request, room_id: str, item_id: int):
        denied = await _authorize(request, room_id, csrf=True)
        if denied:
            return denied
        try:
            payload = TaskItemUpdateInput.model_validate(await request.json())
        except (ValidationError, ValueError, TypeError):
            return api_error_response("入力内容が不正です。", status_code=400)
        try:
            item, updated = await task_data.update_item(
                room_id,
                item_id,
                payload.model_dump(exclude_unset=True, exclude={"version"}),
                payload.version,
            )
        except task_data.InvalidTaskDateRange:
            return api_error_response(
                "開始日は期限日以前の日付を指定してください。", status_code=400
            )
        if item is None:
            return api_error_response("タスクが見つかりません。", status_code=404)
        if not updated:
            return api_error_response(
                "他の画面で更新されました。", status_code=409, data={"item": item}
            )
        return api_ok_response({"item": item})

    @router.delete("/task/{room_id}/items/{item_id}", name="task.delete_item")
    async def delete_task_item(request: Request, room_id: str, item_id: int):
        await enforce_csrf(request)
        backoff_key = f"{get_client_ip(request)}:{room_id}"
        allowed, _, _ = await check_exponential_backoff(
            SCOPE_TASK_ITEM_DELETE, backoff_key
        )
        if not allowed:
            return api_error_response("削除の試行回数が多すぎます。", status_code=429)
        denied = await _authorize(request, room_id)
        if denied:
            await register_exponential_backoff_failure(
                SCOPE_TASK_ITEM_DELETE, backoff_key
            )
            return denied
        deleted = await task_data.delete_item(room_id, item_id)
        await clear_exponential_backoff(SCOPE_TASK_ITEM_DELETE, backoff_key)
        if not deleted:
            return api_error_response("タスクが見つかりません。", status_code=404)
        return api_ok_response({"item_id": item_id})

    @router.post("/task/{room_id}/items/reorder", name="task.reorder_items")
    async def reorder_task_items(request: Request, room_id: str):
        denied = await _authorize(request, room_id, csrf=True)
        if denied:
            return denied
        try:
            payload = TaskReorderInput.model_validate(await request.json())
        except (ValidationError, ValueError, TypeError):
            return api_error_response("入力内容が不正です。", status_code=400)
        items = await task_data.reorder_items(
            room_id, payload.board_status, payload.ordered_item_ids
        )
        if items is None:
            return api_error_response("並び替え対象が不正です。", status_code=400)
        return api_ok_response({"items": items})
