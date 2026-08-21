"""タグの追加・名前変更・削除 API。

分類は「カテゴリ」ではなくタグに統一しているため、タスクの分類を増やしたり
減らしたりする操作はすべてここへ集約する。
Classification is unified on tags, so every add / rename / delete of a label
lives in this router.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import ValidationError

from api_response import api_error_response, api_ok_response
from models import TaskTagInput
from settings import TASK_MAX_TAGS_PER_ROOM
from . import task_data
from .task_authorize import authorize_task_room


def register_task_tag_routes(router: APIRouter) -> None:
    @router.get("/task/{room_id}/tags", name="task.list_tags")
    async def list_task_tags(request: Request, room_id: str):
        denied = await authorize_task_room(request, room_id)
        if denied:
            return denied
        return api_ok_response({"tags": await task_data.list_tags(room_id)})

    @router.post("/task/{room_id}/tags", name="task.create_tag")
    async def create_task_tag(request: Request, room_id: str):
        denied = await authorize_task_room(request, room_id, csrf=True)
        if denied:
            return denied
        try:
            payload = TaskTagInput.model_validate(await request.json())
        except (ValidationError, ValueError, TypeError):
            return api_error_response("タグ名が不正です。", status_code=400)
        try:
            tag = await task_data.create_tag(
                room_id, payload.name, max_tags=TASK_MAX_TAGS_PER_ROOM
            )
        except task_data.TaskTagLimitReached:
            return api_error_response(
                f"タグ数の上限（{TASK_MAX_TAGS_PER_ROOM}件）に達しました。",
                status_code=400,
            )
        return api_ok_response({"tag": tag}, status_code=201)

    @router.patch("/task/{room_id}/tags/{tag_id}", name="task.rename_tag")
    async def rename_task_tag(request: Request, room_id: str, tag_id: int):
        denied = await authorize_task_room(request, room_id, csrf=True)
        if denied:
            return denied
        try:
            payload = TaskTagInput.model_validate(await request.json())
        except (ValidationError, ValueError, TypeError):
            return api_error_response("タグ名が不正です。", status_code=400)
        tag = await task_data.rename_tag(room_id, tag_id, payload.name)
        if tag is None:
            return api_error_response(
                "同じ名前のタグが既にあるか、タグが見つかりません。", status_code=400
            )
        return api_ok_response({"tag": tag})

    @router.delete("/task/{room_id}/tags/{tag_id}", name="task.delete_tag")
    async def delete_task_tag(request: Request, room_id: str, tag_id: int):
        denied = await authorize_task_room(request, room_id, csrf=True)
        if denied:
            return denied
        if not await task_data.delete_tag(room_id, tag_id):
            return api_error_response("タグが見つかりません。", status_code=404)
        return api_ok_response({"tag_id": tag_id})
