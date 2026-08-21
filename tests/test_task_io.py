import json
from unittest.mock import patch, AsyncMock


def test_export_tasks(test_client):
    created = {
        "item_id": 12,
        "title": "Task 1",
        "board_status": "todo",
        "priority": "high",
        "tags": [{"tag_id": 3, "name": "cat1"}],
        "start_date": None,
        "due_date": None,
        "position": 100,
        "version": 0,
        "note": "Note 1",
        "updated_at": "2026-08-15 10:00:00.000000",
        "created_at": "2026-08-15 10:00:00.000000",
    }
    ROOM_META = {
        "room_id": "abc123",
        "id": "abc123",
        "retention_hours": 24,
    }

    with (
        patch("Task.task_authorize.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_io.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_io.task_data.list_items",
            new_callable=AsyncMock,
            return_value=[created],
        ),
    ):
        response = test_client.get("/api/task/abc123/export")

    assert response.status_code == 200
    assert "attachment; filename=" in response.headers["Content-Disposition"]

    data = response.json()
    # 現行形式（タグ）で書き出す。 / Exported in the current tag-based format.
    assert data["version"] == 2
    assert "exported_at" in data
    assert len(data["tasks"]) == 1

    task = data["tasks"][0]
    assert task["title"] == "Task 1"
    assert task["note"] == "Note 1"
    assert task["board_status"] == "todo"
    assert task["priority"] == "high"
    assert task["tags"] == ["cat1"]
    assert "category" not in task
    assert "item_id" not in task
    assert "created_at" not in task


def test_import_tasks_success(test_client):
    import_data = {
        "version": 2,
        "tasks": [
            {
                "title": "Imported 1",
                "note": "",
                "board_status": "doing",
                "priority": "normal",
                "tags": [],
            },
            {
                "title": "Imported 2",
                "note": "Has note",
                "board_status": "done",
                "priority": "low",
                "tags": ["設計", "調査"],
            },
        ],
    }

    ROOM_META = {
        "room_id": "abc123",
        "id": "abc123",
        "retention_hours": 24,
    }

    with (
        patch("Task.task_authorize.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_io.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_io.task_data.count_items",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "Task.task_routes_io.task_data.create_item", new_callable=AsyncMock
        ) as create_item,
    ):
        # By passing an empty CSRF token we bypass web.py CSRF but we also need to mock enforce_csrf if it fails
        pass

    with (
        patch("Task.task_authorize.enforce_csrf", new_callable=AsyncMock),
        patch("Task.task_authorize.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_io.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_io.task_data.count_items",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "Task.task_routes_io.task_data.create_item", new_callable=AsyncMock
        ) as create_item,
        patch(
            "Task.task_routes_io.task_data.resolve_tag_names",
            new_callable=AsyncMock,
            return_value=[7, 8],
        ) as resolve_tag_names,
    ):
        files = {
            "file": ("tasks.json", json.dumps(import_data).encode(), "application/json")
        }
        response = test_client.post("/api/task/abc123/import", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["data"]["imported_count"] == 2
    assert data["data"]["skipped_count"] == 0
    assert create_item.call_count == 2
    # タグ名はルームのタグへ解決してから紐づける
    assert resolve_tag_names.await_args_list[1].args[1] == ["設計", "調査"]
    assert create_item.call_args_list[1].args[1]["tag_ids"] == [7, 8]
    assert "category" not in create_item.call_args_list[1].args[1]


def test_import_tasks_invalid_json(test_client):
    ROOM_META = {
        "room_id": "abc123",
        "id": "abc123",
        "retention_hours": 24,
    }
    with (
        patch("Task.task_authorize.enforce_csrf", new_callable=AsyncMock),
        patch("Task.task_authorize.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_io.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
    ):
        files = {"file": ("tasks.json", b"{invalid json", "application/json")}
        response = test_client.post("/api/task/abc123/import", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "無効なJSON" in data["error"]


def test_import_tasks_rejects_non_object_json(test_client):
    """JSON のトップレベルが配列でも 500 ではなく入力エラーにする。"""
    ROOM_META = {
        "room_id": "abc123",
        "id": "abc123",
        "retention_hours": 24,
    }
    with (
        patch("Task.task_authorize.enforce_csrf", new_callable=AsyncMock),
        patch("Task.task_authorize.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_io.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
    ):
        files = {"file": ("tasks.json", b"[]", "application/json")}
        response = test_client.post("/api/task/abc123/import", files=files)

    assert response.status_code == 400
    assert "タスクリストの形式が不正" in response.json()["error"]


def test_import_tasks_invalid_version(test_client):
    ROOM_META = {
        "room_id": "abc123",
        "id": "abc123",
        "retention_hours": 24,
    }
    import_data = {"version": 3, "tasks": []}
    with (
        patch("Task.task_authorize.enforce_csrf", new_callable=AsyncMock),
        patch("Task.task_authorize.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_io.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
    ):
        files = {
            "file": ("tasks.json", json.dumps(import_data).encode(), "application/json")
        }
        response = test_client.post("/api/task/abc123/import", files=files)

    assert response.status_code == 400
    assert "サポートされていないバージョン" in response.json()["error"]


def test_import_tasks_accepts_legacy_category_files(test_client):
    """旧形式（version 1）の category は、同名のタグとして取り込む。"""
    ROOM_META = {
        "room_id": "abc123",
        "id": "abc123",
        "retention_hours": 24,
    }
    import_data = {
        "version": 1,
        "tasks": [
            {
                "title": "旧形式のタスク",
                "note": "",
                "board_status": "todo",
                "priority": "normal",
                "category": "機能開発",
            }
        ],
    }

    with (
        patch("Task.task_authorize.enforce_csrf", new_callable=AsyncMock),
        patch("Task.task_authorize.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_io.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_io.task_data.count_items",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "Task.task_routes_io.task_data.create_item", new_callable=AsyncMock
        ) as create_item,
        patch(
            "Task.task_routes_io.task_data.resolve_tag_names",
            new_callable=AsyncMock,
            return_value=[21],
        ) as resolve_tag_names,
    ):
        files = {
            "file": ("tasks.json", json.dumps(import_data).encode(), "application/json")
        }
        response = test_client.post("/api/task/abc123/import", files=files)

    assert response.status_code == 200
    assert response.json()["data"]["imported_count"] == 1
    resolve_tag_names.assert_awaited_once()
    assert resolve_tag_names.await_args.args[1] == ["機能開発"]
    assert create_item.call_args.args[1]["tag_ids"] == [21]
