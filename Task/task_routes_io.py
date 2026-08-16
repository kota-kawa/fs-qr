import json
from datetime import datetime, timezone

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from api_response import api_error_response, api_ok_response
from models import TaskItemInput
from settings import TASK_MAX_ITEMS_PER_ROOM
from web import enforce_csrf
from . import task_data
from .task_access import has_task_room_access


def register_task_io_routes(router: APIRouter) -> None:
    @router.get("/task/{room_id}/export", name="task.export_items")
    async def export_task_items(request: Request, room_id: str):
        if not has_task_room_access(request, room_id):
            return api_error_response("room access is not established", status_code=404)
        if not await task_data.get_room_meta_direct(room_id):
            return api_error_response("room expired or deleted", status_code=404)

        items = await task_data.list_items(room_id)

        export_tasks = []
        for item in items:
            export_item = {
                "title": item["title"],
                "note": item["note"],
                "board_status": item["board_status"],
                "priority": item["priority"],
                "category": item["category"],
                "start_date": item["start_date"],
                "due_date": item["due_date"],
                "position": item["position"],
            }
            export_tasks.append(export_item)

        export_data = {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tasks": export_tasks,
        }

        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"tasks-{room_id[:8]}-{date_str}.json"

        return JSONResponse(
            content=export_data,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/task/{room_id}/import", name="task.import_items")
    async def import_task_items(
        request: Request, room_id: str, file: UploadFile = File(...)
    ):
        await enforce_csrf(request)
        if not has_task_room_access(request, room_id):
            return api_error_response("room access is not established", status_code=404)
        if not await task_data.get_room_meta_direct(room_id):
            return api_error_response("room expired or deleted", status_code=404)

        content = await file.read()
        if len(content) > 1024 * 1024:
            return api_error_response(
                "ファイルサイズが1MBを超えています。", status_code=400
            )

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return api_error_response("無効なJSONファイルです。", status_code=400)

        if data.get("version") != 1:
            return api_error_response(
                "サポートされていないバージョンです。", status_code=400
            )

        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return api_error_response("タスクリストの形式が不正です。", status_code=400)

        current_count = await task_data.count_items(room_id)
        if current_count + len(tasks) > TASK_MAX_ITEMS_PER_ROOM:
            return api_error_response("タスク数の上限に達します。", status_code=400)

        imported_count = 0
        skipped_count = 0

        for task_data_raw in tasks:
            try:
                payload = TaskItemInput.model_validate(task_data_raw)
                item_values = payload.model_dump()
                await task_data.create_item(room_id, item_values)
                imported_count += 1
            except (ValidationError, ValueError, TypeError):
                skipped_count += 1

        return api_ok_response(
            {"imported_count": imported_count, "skipped_count": skipped_count}
        )
