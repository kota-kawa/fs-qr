"""Task サービスのルーム操作とアイテム API の回帰テスト。"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


ROOM_META = {
    "room_id": "abc123",
    "id": "abc123",
    "retention_hours": 24,
    "expires_at": datetime(2026, 8, 16, 12, 0, 0),
}
ITEM = {
    "item_id": 12,
    "title": "資料をまとめる",
    "note": "",
    "board_status": "todo",
    "priority": "normal",
    "category": "仕事",
    "due_date": None,
    "position": 100,
    "version": 0,
    "updated_at": "2026-08-15 10:00:00.000000",
}


def test_task_pages(test_client: TestClient):
    """Task の公開・操作ページが表示できる。"""
    for path in (
        "/task_menu",
        "/shared-task",
        "/task",
        "/create_task_room",
        "/search_task",
    ):
        assert test_client.get(path).status_code == 200


def test_create_task_room_rejects_invalid_manual_id(test_client: TestClient):
    for room_id in ("", "abc!@#", "abcde"):
        response = test_client.post(
            "/create_task_room", json={"id": room_id, "idMode": "manual"}
        )
        assert response.status_code == 400
        assert response.json()["status"] == "error"


def test_create_task_room_returns_room_credentials_for_fetch(test_client: TestClient):
    create_room = AsyncMock()
    with (
        patch("Task.task_routes_room.generate_room_password", return_value="000042"),
        patch(
            "Task.task_routes_room.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("Task.task_routes_room.task_data.create_room", create_room),
        patch(
            "Task.task_routes_room.create_share_link",
            new_callable=AsyncMock,
            return_value="task-share-token",
        ),
    ):
        response = test_client.post(
            "/create_task_room",
            data={"id": "abc123", "idMode": "manual", "retention_hours": 24},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["redirect_url"] == "/task/r/abc123"
    assert payload["data"]["share_url"].endswith("/task/s/task-share-token")
    assert payload["data"]["password"] == "000042"
    # LP の共有パネルとタスク投入APIが参照できるよう room_id も返す
    assert payload["data"]["room_id"] == "abc123"
    create_room.assert_awaited_once_with("abc123", "000042", "abc123", 24)


def test_create_task_room_accepts_one_month_retention(test_client: TestClient):
    """Task は1日・1週間・1か月の保存期間を選択できる（Groupより長期に対応）。"""
    create_room = AsyncMock()
    with (
        patch("Task.task_routes_room.generate_room_password", return_value="000042"),
        patch(
            "Task.task_routes_room.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("Task.task_routes_room.task_data.create_room", create_room),
        patch(
            "Task.task_routes_room.create_share_link",
            new_callable=AsyncMock,
            return_value="task-share-token",
        ),
    ):
        response = test_client.post(
            "/create_task_room",
            data={"id": "abc123", "idMode": "manual", "retention_hours": 720},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    create_room.assert_awaited_once_with("abc123", "000042", "abc123", 720)


def test_create_task_room_rejects_legacy_short_retention(test_client: TestClient):
    """Group専用の旧選択肢（6時間・12時間）はTaskでは1日にフォールバックする。"""
    create_room = AsyncMock()
    with (
        patch("Task.task_routes_room.generate_room_password", return_value="000042"),
        patch(
            "Task.task_routes_room.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("Task.task_routes_room.task_data.create_room", create_room),
        patch(
            "Task.task_routes_room.create_share_link",
            new_callable=AsyncMock,
            return_value="task-share-token",
        ),
    ):
        response = test_client.post(
            "/create_task_room",
            data={"id": "abc123", "idMode": "manual", "retention_hours": 12},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    create_room.assert_awaited_once_with("abc123", "000042", "abc123", 24)


def test_task_share_entry_rejects_invalid_token(test_client: TestClient):
    with (
        patch(
            "Task.task_routes_room.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Task.task_routes_room.resolve_share_link",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "Task.task_routes_room.register_failure",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
    ):
        response = test_client.get("/task/s/invalid-token")
    assert response.status_code == 404


def test_task_board_requires_remembered_access(test_client: TestClient):
    assert test_client.get("/task/r/abc123").status_code == 404


def test_task_item_api_requires_access_and_csrf(test_client: TestClient):
    assert test_client.get("/api/task/abc123/items").status_code == 404

    async def request_without_csrf():
        return await test_client._raw_request(
            "POST", "/api/task/abc123/items", json={"title": "新しいタスク"}
        )

    with patch("Task.task_routes_items.has_task_room_access", return_value=True):
        response = asyncio.run(request_without_csrf())
    assert response.status_code == 403


def test_task_item_crud_routes(test_client: TestClient):
    created = {**ITEM, "version": 0}
    updated = {**ITEM, "title": "更新後", "version": 1}
    with (
        patch("Task.task_routes_items.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_items.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_items.task_data.count_items",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "Task.task_routes_items.task_data.create_item",
            new_callable=AsyncMock,
            return_value=created,
        ),
        patch(
            "Task.task_routes_items.task_data.list_items",
            new_callable=AsyncMock,
            return_value=[created],
        ),
        patch(
            "Task.task_routes_items.task_data.list_categories",
            new_callable=AsyncMock,
            return_value=["仕事"],
        ),
        patch(
            "Task.task_routes_items.task_data.update_item",
            new_callable=AsyncMock,
            return_value=(updated, True),
        ),
        patch(
            "Task.task_routes_items.task_data.delete_item", new_callable=AsyncMock
        ) as delete_item,
        patch(
            "Task.task_routes_items.check_exponential_backoff",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Task.task_routes_items.clear_exponential_backoff",
            new_callable=AsyncMock,
        ),
    ):
        create_response = test_client.post(
            "/api/task/abc123/items", json={"title": "資料をまとめる"}
        )
        list_response = test_client.get("/api/task/abc123/items")
        update_response = test_client.request(
            "PATCH", "/api/task/abc123/items/12", json={"version": 0, "title": "更新後"}
        )
        delete_response = test_client.delete("/api/task/abc123/items/12")

    assert create_response.status_code == 201
    assert create_response.json()["data"]["item"] == created
    assert list_response.json()["data"] == {"items": [created], "categories": ["仕事"]}
    assert update_response.json()["data"]["item"] == updated
    assert delete_response.status_code == 200
    delete_item.assert_awaited_once_with("abc123", 12)


def test_task_item_limit_validation_and_conflict(test_client: TestClient):
    with (
        patch("Task.task_routes_items.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_items.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_items.task_data.count_items",
            new_callable=AsyncMock,
            return_value=200,
        ),
    ):
        limit_response = test_client.post(
            "/api/task/abc123/items", json={"title": "上限確認"}
        )

    with (
        patch("Task.task_routes_items.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_items.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_items.task_data.update_item",
            new_callable=AsyncMock,
            return_value=({**ITEM, "version": 4}, False),
        ),
    ):
        conflict_response = test_client.request(
            "PATCH", "/api/task/abc123/items/12", json={"version": 3, "title": "競合"}
        )
        invalid_response = test_client.request(
            "PATCH",
            "/api/task/abc123/items/12",
            json={"version": 3, "board_status": "unknown"},
        )

    assert limit_response.status_code == 400
    assert conflict_response.status_code == 409
    assert conflict_response.json()["data"]["item"]["version"] == 4
    assert invalid_response.status_code == 400


def test_task_reorder_rejects_invalid_ids_and_returns_column(test_client: TestClient):
    with (
        patch("Task.task_routes_items.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_items.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_items.task_data.reorder_items",
            new_callable=AsyncMock,
            side_effect=[None, [{**ITEM, "board_status": "doing", "position": 100}]],
        ),
    ):
        invalid_response = test_client.post(
            "/api/task/abc123/items/reorder",
            json={"board_status": "doing", "ordered_item_ids": [999]},
        )
        success_response = test_client.post(
            "/api/task/abc123/items/reorder",
            json={"board_status": "doing", "ordered_item_ids": [12]},
        )

    assert invalid_response.status_code == 400
    assert success_response.status_code == 200
    assert success_response.json()["data"]["items"][0]["position"] == 100


def test_task_board_page_renders_ux_elements(test_client: TestClient):
    """タスクボード画面に進捗サマリーと操作UIが描画される。"""
    with (
        patch("Task.task_routes_room.has_task_room_access", return_value=True),
        patch("Task.task_routes_room.can_delete_task_room", return_value=True),
        patch("Task.task_routes_room.get_task_room_password", return_value="pw12345"),
        patch(
            "Task.task_routes_room.get_task_room_share_token",
            return_value="sharetoken123",
        ),
        patch(
            "Task.task_routes_room.get_room_if_active",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
    ):
        response = test_client.get("/task/r/abc123")

    assert response.status_code == 200
    body = response.text

    # 進捗サマリーと期限フィルターのチップ
    for marker in (
        'id="taskProgressBar"',
        'id="taskProgressFill"',
        'data-due-filter="overdue"',
        'data-due-filter="today"',
        'data-due-filter="week"',
    ):
        assert marker in body

    # 進捗・共有・操作は1つのコンソールへ集約されている
    assert '<section class="task-console"' in body
    assert '<div class="task-console__overview">' in body
    assert '<div class="task-console__controls">' in body

    # 共有情報は折りたたみ、ボードが先に見える構成
    assert '<details class="task-room-details" id="taskRoomDetails">' in body
    assert '<summary class="task-room-details__summary">' in body
    assert body.index('id="taskBoard"') > body.index('id="taskRoomDetails"')

    # カラムごとのインライン追加・操作メニュー・スマホ用タブ
    assert 'id="taskStatusTabs" role="group"' in body
    assert 'data-mobile-view="all" aria-pressed="true"' in body
    for status in ("todo", "doing", "done"):
        assert f'data-column-add="{status}"' in body
        assert f'data-column-menu="{status}"' in body
        assert f'data-inline-add-for="{status}"' in body
        assert f'data-mobile-view="{status}"' in body

    # 絞り込みパネルとショートカットヘルプ
    for marker in (
        'id="taskFilterPanel"',
        'id="taskDueFilter"',
        'id="taskShortcutDialog"',
        'id="taskEditorDialog"',
    ):
        assert marker in body

    # クイック追加ボタンに plus アイコンが描画されている
    assert 'class="modern-btn task-btn task-btn--add"' in body
    assert (
        '<path fill-rule="evenodd" d="M12 3.75a.75.75 0 0 1 .75.75v6.75h6.75a.75.75 0 0 1 0 1.5h-6.75v6.75a.75.75 0 0 1-1.5 0v-6.75H4.5a.75.75 0 0 1 0-1.5h6.75V4.5a.75.75 0 0 1 .75-.75Z" clip-rule="evenodd" />'
        in body
    )

    # 編集ダイアログの保存ボタンから Ctrl+Enter のヒント表示が削除されている
    assert '<button type="submit" class="modern-btn task-btn">保存する</button>' in body


def test_task_board_page_loads_all_board_modules(test_client: TestClient):
    """ボードのJSモジュールが依存順にすべて読み込まれる。"""
    with (
        patch("Task.task_routes_room.has_task_room_access", return_value=True),
        patch("Task.task_routes_room.can_delete_task_room", return_value=False),
        patch("Task.task_routes_room.get_task_room_password", return_value=""),
        patch("Task.task_routes_room.get_task_room_share_token", return_value="tok"),
        patch(
            "Task.task_routes_room.get_room_if_active",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
    ):
        response = test_client.get("/task/r/abc123")

    assert response.status_code == 200
    body = response.text

    modules = [
        "core.js",
        "store.js",
        "select.js",
        "filters.js",
        "render.js",
        "menu.js",
        "actions.js",
        "columns.js",
        "editor.js",
        "dnd.js",
        "calendar.js",
        "views.js",
        "main.js",
    ]
    namespace_position = body.index("js/shared/app-namespace.js")
    config_position = body.index("setConfig('taskBoard'")
    positions = [body.index(f"js/task_board/{name}") for name in modules]
    assert namespace_position < config_position < positions[0]
    assert positions == sorted(positions)


def test_task_board_page_renders_custom_dropdown_targets(test_client: TestClient):
    """タスクボード内の6つのセレクト要素がカスタムドロップダウン対象として描画される。"""
    with (
        patch("Task.task_routes_room.has_task_room_access", return_value=True),
        patch("Task.task_routes_room.can_delete_task_room", return_value=False),
        patch("Task.task_routes_room.get_task_room_password", return_value=""),
        patch("Task.task_routes_room.get_task_room_share_token", return_value="tok"),
        patch(
            "Task.task_routes_room.get_room_if_active",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
    ):
        response = test_client.get("/task/r/abc123")

    assert response.status_code == 200
    body = response.text

    # 対象の6つのドロップダウン要素が存在し、task-select-pill クラスを持つ
    target_select_ids = (
        "taskCreatePriority",
        "taskCategoryFilter",
        "taskPriorityFilter",
        "taskDueFilter",
        "taskSortSelect",
        "taskEditorPriority",
    )
    for select_id in target_select_ids:
        assert f'id="{select_id}"' in body
        assert 'class="task-select-pill' in body


def test_task_board_page_renders_calendar_view(test_client: TestClient):
    """ボード表示とカレンダー表示を切り替えるUIが描画される。"""
    with (
        patch("Task.task_routes_room.has_task_room_access", return_value=True),
        patch("Task.task_routes_room.can_delete_task_room", return_value=False),
        patch("Task.task_routes_room.get_task_room_password", return_value=""),
        patch("Task.task_routes_room.get_task_room_share_token", return_value="tok"),
        patch(
            "Task.task_routes_room.get_room_if_active",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
    ):
        response = test_client.get("/task/r/abc123")

    assert response.status_code == 200
    body = response.text

    # 表示切り替えのセグメント
    assert 'data-view-switch="board"' in body
    assert 'data-view-switch="calendar"' in body

    # カレンダー本体は初期状態では非表示
    assert '<section class="task-calendar" id="taskCalendar"' in body
    assert 'id="taskCalendar" aria-label="カレンダー表示" hidden' in body

    # 月移動・選択日パネル・期限なしパネル
    for marker in (
        'data-calendar-nav="-1"',
        'data-calendar-nav="1"',
        'id="taskCalendarToday"',
        'id="taskCalendarGrid"',
        'id="taskCalendarDayList"',
        'id="taskCalendarAdd"',
        'id="taskCalendarBacklogList"',
    ):
        assert marker in body


def test_task_calendar_span_assets(test_client: TestClient):
    """カレンダーの期間バー（開始日〜締切日スパン）用スクリプトとスタイルが揃っている。"""
    from pathlib import Path
    from Task.task_data import _serialize_item

    # 1. アイテムのシリアライズで created_at と due_date が日付として扱える形式で出力されること
    sample_row = {
        "item_id": 10,
        "title": "タスク期間テスト",
        "note": "",
        "board_status": "doing",
        "priority": "high",
        "category": "開発",
        "due_date": datetime(2026, 8, 20).date(),
        "created_at": datetime(2026, 8, 16, 10, 0, 0),
        "updated_at": datetime(2026, 8, 16, 10, 0, 0),
    }
    serialized = _serialize_item(sample_row)
    assert serialized["created_at"].startswith("2026-08-16")
    assert serialized["due_date"] == "2026-08-20"

    # 2. calendar.js に期間算出・スパンバー・締切日テキスト制御ロジックが含まれること
    cal_js_path = Path("static/js/task_board/calendar.js")
    assert cal_js_path.exists()
    js_content = cal_js_path.read_text(encoding="utf-8")
    for keyword in (
        "getItemSpan",
        "groupByDateSpan",
        "is-span-bar",
        "is-span-start",
        "is-span-mid",
        "is-span-end",
        "is-single",
    ):
        assert keyword in js_content

    # 3. 16-task-board.css に期間バー（is-span-bar, is-span-start/mid/end）のスタイルが定義されていること
    css_path = Path("static/css/16-task-board.css")
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")
    for css_class in (
        ".task-calendar__chip.is-span-bar",
        ".task-calendar__chip.is-span-start",
        ".task-calendar__chip.is-span-mid",
        ".task-calendar__chip.is-span-end",
        ".task-calendar__chip.is-single",
    ):
        assert css_class in css_content
