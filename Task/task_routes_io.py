import json
from datetime import datetime, timezone

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from api_response import api_error_response, api_ok_response
from models import TaskItemInput
from settings import TASK_MAX_ITEMS_PER_ROOM, TASK_MAX_TAGS_PER_ROOM
from . import task_data
from .task_authorize import authorize_task_room

# エクスポート形式のバージョン。
# 1: category（単一のカテゴリ文字列）を持つ旧形式。読み込みのみ対応する。
# 2: tags（タグ名の配列）を持つ現行形式。
# Version 1 files carry a single "category" string and stay importable; version 2
# is the current tag-based format.
EXPORT_VERSION = 2
SUPPORTED_IMPORT_VERSIONS = (1, 2)


def _with_tags(raw: object) -> object:
    """旧形式（version 1）の category をタグ1件として読み替える。

    Maps the legacy single "category" of a version 1 file onto the tag list so
    previously exported boards stay importable.
    """
    if not isinstance(raw, dict):
        return raw
    if raw.get("tags") or not raw.get("category"):
        return raw
    converted = dict(raw)
    converted["tags"] = [converted["category"]]
    return converted


def register_task_io_routes(router: APIRouter) -> None:  # noqa: C901
    @router.get("/task/{room_id}/export", name="task.export_items")
    async def export_task_items(request: Request, room_id: str):
        denied = await authorize_task_room(request, room_id)
        if denied:
            return denied

        items = await task_data.list_items(room_id)

        export_tasks = []
        for item in items:
            export_item = {
                "title": item["title"],
                "note": item["note"],
                "board_status": item["board_status"],
                "priority": item["priority"],
                # タグは名前で書き出す。別ルームへ取り込んでも意味が保たれる。
                # Tags are exported by name so an import into another room keeps meaning.
                "tags": [tag["name"] for tag in item.get("tags") or []],
                "start_date": item["start_date"],
                "due_date": item["due_date"],
                "position": item["position"],
            }
            export_tasks.append(export_item)

        export_data = {
            "version": EXPORT_VERSION,
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
        denied = await authorize_task_room(request, room_id, csrf=True)
        if denied:
            return denied

        content = await file.read()
        if len(content) > 1024 * 1024:
            return api_error_response(
                "ファイルサイズが1MBを超えています。", status_code=400
            )

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return api_error_response("無効なJSONファイルです。", status_code=400)

        if not isinstance(data, dict):
            return api_error_response("タスクリストの形式が不正です。", status_code=400)

        if data.get("version") not in SUPPORTED_IMPORT_VERSIONS:
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
                payload = TaskItemInput.model_validate(_with_tags(task_data_raw))
                item_values = payload.model_dump(exclude={"tags"})
                item_values["tag_ids"] = await task_data.resolve_tag_names(
                    room_id, payload.tags, max_tags=TASK_MAX_TAGS_PER_ROOM
                )
                await task_data.create_item(
                    room_id, item_values, max_items=TASK_MAX_ITEMS_PER_ROOM
                )
                imported_count += 1
            except (ValidationError, ValueError, TypeError):
                skipped_count += 1

        return api_ok_response(
            {"imported_count": imported_count, "skipped_count": skipped_count}
        )
