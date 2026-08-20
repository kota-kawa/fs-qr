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
    "board_status": "todo",
    "priority": "normal",
    "category": "仕事",
    "start_date": None,
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


def test_task_item_date_validation(test_client: TestClient):
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
    ):
        # Invalid date combinations
        invalid_response = test_client.post(
            "/api/task/abc123/items",
            json={
                "title": "日付エラー",
                "start_date": "2026-08-20",
                "due_date": "2026-08-15",
            },
        )
        assert invalid_response.status_code == 400

        invalid_format_response = test_client.post(
            "/api/task/abc123/items",
            json={"title": "存在しない日付", "due_date": "2026-02-30"},
        )
        assert invalid_format_response.status_code == 400


def test_task_item_update_rejects_partial_date_range_conflict(test_client: TestClient):
    """片方の日付だけの更新でも既存値との前後関係を守る。"""
    from Task import task_data

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
            side_effect=task_data.InvalidTaskDateRange(),
        ),
    ):
        response = test_client.request(
            "PATCH",
            "/api/task/abc123/items/12",
            json={"version": 0, "due_date": "2026-08-15"},
        )

    assert response.status_code == 400
    assert "開始日は期限日以前" in response.json()["error"]


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


def test_task_item_create_rechecks_limit_inside_data_layer(test_client: TestClient):
    from Task import task_data

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
            side_effect=task_data.TaskItemLimitReached(),
        ),
    ):
        response = test_client.post(
            "/api/task/abc123/items", json={"title": "競合追加"}
        )

    assert response.status_code == 400
    assert "タスク数の上限" in response.json()["error"]


def test_task_delete_reports_missing_item(test_client: TestClient):
    with (
        patch("Task.task_routes_items.has_task_room_access", return_value=True),
        patch(
            "Task.task_routes_items.task_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=ROOM_META,
        ),
        patch(
            "Task.task_routes_items.task_data.delete_item",
            new_callable=AsyncMock,
            return_value=False,
        ),
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
        response = test_client.delete("/api/task/abc123/items/12")

    assert response.status_code == 404
    assert "タスクが見つかりません" in response.json()["error"]


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
        "calendar-layout.js",
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


def test_task_board_page_renders_toolbar_export_import_buttons(test_client: TestClient):
    """エクスポート/インポートボタンが周囲の pill 型 UI に揃った専用クラスで描画される。"""
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

    # io.js が参照する id は維持したまま、汎用ボタンではなく専用の pill 型クラスへ置き換える
    assert 'id="taskExportBtn"' in body
    assert 'id="taskImportBtn"' in body
    assert 'id="taskImportInput"' in body
    assert 'class="task-toolbar-btn"' in body
    assert "modern-btn task-btn-secondary" not in body

    # 矢印記号のベタ書きやインラインスタイルは残っていない
    assert "↓ エクスポート" not in body
    assert "↑ インポート" not in body
    assert 'style="cursor:pointer"' not in body

    # label はキーボード操作可能（tabindex 付与）で、file input の id は維持される
    assert (
        'id="taskImportBtn" class="task-toolbar-btn" title="タスクをインポート" aria-label="タスクをインポート" tabindex="0"'
        in body
    )

    # Enter / Space の処理はインラインハンドラーではなく io.js に置く
    from pathlib import Path

    assert "onkeydown=" not in body
    io_js = Path("static/js/task_board/io.js").read_text(encoding="utf-8")
    assert "taskImportBtn" in io_js
    assert "importInput.click()" in io_js


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
    """カレンダーの期間タスクが、開始日〜締切日をまたぐ「連続した1本の帯」として
    描画されるためのロジックとスタイルが揃っていることを検証する。

    週境界をまたぐ場合にセグメント分割・レーン割り当てを行う設計になっているため、
    座標やクラス名の実装詳細ではなく、責務ごとに切り出された関数名・クラス名・
    CSS変数の「存在」を確認する（実装の細部が変わってもテストが壊れにくいように）。
    """
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
        "start_date": datetime(2026, 8, 18).date(),
        "due_date": datetime(2026, 8, 20).date(),
        "created_at": datetime(2026, 8, 16, 10, 0, 0),
        "updated_at": datetime(2026, 8, 16, 10, 0, 0),
    }
    serialized = _serialize_item(sample_row)
    assert serialized["created_at"].startswith("2026-08-16")
    assert serialized["start_date"] == "2026-08-18"
    assert serialized["due_date"] == "2026-08-20"

    # 2. calendar-layout.js に「週分割」「レーン割り当て」の純粋関数が存在すること
    #    （期間バーがセル境界をまたいで連続して見えるようにする核となるロジック）
    layout_js_path = Path("static/js/task_board/calendar-layout.js")
    assert layout_js_path.exists()
    layout_js = layout_js_path.read_text(encoding="utf-8")
    for keyword in (
        "function getItemSpan(",
        "function groupByDateSpan(",
        "function buildMonthWeeks(",
        "function assignLanes(",
        "function layoutWeekBars(",
        "isSegStart",
        "isSegEnd",
        "continuesBefore",
        "continuesAfter",
    ):
        assert keyword in layout_js, f"calendar-layout.js に {keyword} が見つかりません"

    # 3. calendar.js が calendar-layout.js のレイアウト計算結果を使って
    #    週行（week）・バー要素・単日チップを組み立てていること
    cal_js_path = Path("static/js/task_board/calendar.js")
    assert cal_js_path.exists()
    js_content = cal_js_path.read_text(encoding="utf-8")
    for keyword in (
        "modules.calendarLayout",
        "layout.buildMonthWeeks",
        "layout.assignLanes",
        "layout.layoutWeekBars",
        "function createWeek(",
        "function createBar(",
        "function createCell(",
        "task-calendar__week",
        "task-calendar__bars",
        "is-multi",
        "is-single",
        "MAX_LANES",
    ):
        assert keyword in js_content, f"calendar.js に {keyword} が見つかりません"

    # 4. 16-task-board.css に「週行」「バーのオーバーレイ」「連続バー要素」の
    #    構造クラス、および開始端・終了端・週継続を表す修飾クラスが定義されていること
    css_path = Path("static/css/16-task-board.css")
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")
    for css_selector in (
        ".task-calendar__week {",
        ".task-calendar__bars {",
        ".task-calendar__period-bar {",
        ".task-calendar__period-bar.is-multi",
        ".task-calendar__period-bar.is-multi.is-bar-start",
        ".task-calendar__period-bar.is-multi.is-bar-end",
        ".task-calendar__period-bar.is-multi.is-continues-before",
        ".task-calendar__period-bar.is-multi.is-continues-after",
        ".task-calendar__period-bar.is-single",
        "--task-cal-lanes",
    ):
        assert css_selector in css_content, (
            f"16-task-board.css に {css_selector} が見つかりません"
        )

    # 5. 終端（締切日）に矢じり（右向き三角）を描く clip-path ルールが存在すること
    assert "clip-path: polygon" in css_content
    assert ".is-bar-end {" in css_content

    # 6. clip-path は左右両端の形を1プロパティで決めるため、左端×右端の4通りを
    #    個別に宣言しておく必要がある。単一クラスのルールに分けると後勝ちで
    #    片方が打ち消され、「前の週から続いて今週で終わる」バーの矢じりが消える。
    for combination in (
        ".task-calendar__period-bar.is-multi.is-bar-start.is-bar-end {",
        ".task-calendar__period-bar.is-multi.is-bar-start.is-continues-after {",
        ".task-calendar__period-bar.is-multi.is-continues-before.is-bar-end {",
        ".task-calendar__period-bar.is-multi.is-continues-before.is-continues-after {",
    ):
        assert combination in css_content, (
            f"16-task-board.css に端形状の組み合わせ {combination} が見つかりません"
        )


def test_task_undo_preserves_start_date_and_quick_add_is_single_flight():
    """削除取り消しとクイック追加の重複防止が開始日を壊さない。"""
    from pathlib import Path

    actions_js = Path("static/js/task_board/actions.js").read_text(encoding="utf-8")
    main_js = Path("static/js/task_board/main.js").read_text(encoding="utf-8")
    core_js = Path("static/js/task_board/core.js").read_text(encoding="utf-8")

    assert "start_date: item.start_date || null" in actions_js
    assert "var isCreatingQuickAdd = false;" in main_js
    assert "if (isCreatingQuickAdd) return;" in main_js
    assert "dueDate.getFullYear() !== year" in core_js


def test_task_calendar_item_color(test_client: TestClient):
    """カレンダーの期間バー・単日チップにタスク固有識別色が適用され、
    is-done/is-doing/is-overdue の状態表現が維持されていることを検証する。
    """
    from pathlib import Path

    cal_js_path = Path("static/js/task_board/calendar.js")
    assert cal_js_path.exists()
    js_content = cal_js_path.read_text(encoding="utf-8")

    # 1. TASK_PALETTE 配列が定義されていること（12色）
    assert "TASK_PALETTE" in js_content
    # 12色のうち代表色が含まれること
    for color in ("#2563eb", "#059669", "#dc2626", "#9333ea"):
        assert color in js_content

    # 2. taskColor() ヘルパー関数が実装されていること
    assert "function taskColor(" in js_content
    assert "item_id" in js_content
    assert "TASK_PALETTE.length" in js_content

    # 3. createBar() で --task-item-color CSS変数が設定されること
    assert "--task-item-color" in js_content
    assert "style.setProperty" in js_content
    assert "taskColor(item)" in js_content

    css_path = Path("static/css/16-task-board.css")
    assert css_path.exists()
    css_content = css_path.read_text(encoding="utf-8")

    # 4. CSS側で --task-item-color 変数が期間バー・単日チップの背景/ボーダーに使われていること
    assert "var(--task-item-color" in css_content
    assert "background: var(--task-item-color" in css_content
    assert "border-left: 3px solid var(--task-item-color" in css_content

    # 5. done状態が opacity フェードで表現されること
    assert ".task-calendar__period-bar.is-done {" in css_content
    assert "opacity: 0.65" in css_content

    # 6. overdue状態が赤系強調（!important 付き）で上書きされること
    assert ".task-calendar__period-bar.is-overdue {" in css_content
    assert "var(--task-high) !important" in css_content

    # 7. doing状態のスタイルが定義されていること
    assert ".task-calendar__period-bar.is-doing {" in css_content

    # 8. 矢じり（arrow head）を描く clip-path ルールが is-bar-end に適用されていること
    assert ".task-calendar__period-bar.is-multi.is-bar-end {" in css_content
    assert "clip-path: polygon" in css_content

    # 9. 週境界をまたぐ場合の継続修飾クラス（フラット化・ノッチ）が定義されていること
    assert ".task-calendar__period-bar.is-multi.is-continues-before {" in css_content
    assert ".task-calendar__period-bar.is-multi.is-continues-after {" in css_content


def test_task_board_fixed_overlays_survive_body_relative_override():
    """body 直下に追加される固定表示UI（ツールチップ・トースト等）が、
    タスクページ全体を relative 化する基底スタイルに負けないことを確認する。

    01-base-search.css の `body.task-section > *` は、装飾用の背景グラデーション
    （::before）の上に本文を重ねるため、body の直接の子要素すべてへ
    `position: relative; z-index: 1;` を強制する。このセレクタの詳細度
    (要素+クラス+ユニバーサル = 0,1,1) は、共通UIレイヤーが単一クラスで
    書いた `position: fixed`（0,1,0）より高く、ソースの記述順に関係なく
    後者を上書きしてしまう。

    影響を受けるのは、いずれも document.body へ直接 appendChild される要素:
      - .fsqr-tooltip       (static/tooltip.js: title属性ホバー時のツールチップ)
      - .fsqr-progress      (static/js/shared/ux-runtime.js: 画面上部の進捗バー)
      - .fsqr-toast-stack   (同上: トースト通知コンテナ)
      - .fsqr-offline-banner(同上: オフラインバナー)

    これらが relative 化されると、
      1) タスクカードのボタン等（title属性あり）にホバーするたびに
         ツールチップが通常のドキュメントフローへ挿入され、body の高さが
         変化してページ全体が縦にガタつく。
      2) タスク削除後の完了トーストが画面に固定されず、body の末尾
         （フッターの下）に描画され、スクロールしないと見えない。

    16-task-board.css は既存の `.task-menu` / `.task-card--ghost` と同様、
    より詳細度の高い `.task-section > .selector { position: fixed; }` で
    上書きしている必要がある。
    """
    from pathlib import Path

    base_css = Path("static/css/01-base-search.css").read_text(encoding="utf-8")
    assert "body.task-section > *" in base_css, (
        "前提となる body.task-section > * { position: relative; } のルールが"
        " 01-base-search.css から見つかりません（テストの前提が崩れています）"
    )

    css_content = Path("static/css/16-task-board.css").read_text(encoding="utf-8")

    # 既存の overlay 要素（.task-menu / .task-card--ghost）に加えて、
    # 共通UIレイヤーが body 直下へ追加する要素も fixed へ上書きされていること
    for selector in (
        ".task-section > .task-menu",
        ".task-section > .task-card--ghost",
        ".task-section > .fsqr-tooltip",
        ".task-section > .fsqr-progress",
        ".task-section > .fsqr-toast-stack",
        ".task-section > .fsqr-offline-banner",
    ):
        assert selector in css_content, (
            f"16-task-board.css に {selector} の position:fixed 上書きが見つかりません"
        )

    # 上記セレクタが実際に position: fixed を宣言している「Body-level overlays」
    # ブロック内に含まれていること、および z-index も
    # body.task-section > * { z-index: 1; } に埋もれないよう明示的に
    # 再宣言されていることを確認する
    body_overlay_start = css_content.index("Body-level overlays")
    body_overlay_block = css_content[body_overlay_start : body_overlay_start + 2400]
    assert "position: fixed;" in body_overlay_block
    assert "var(--z-tooltip" in body_overlay_block
    assert "var(--z-toast" in body_overlay_block

    # テストの前提となるクラス名・appendChild 先が実装側と一致していること
    ux_runtime_js = Path("static/js/shared/ux-runtime.js").read_text(encoding="utf-8")
    assert 'className = "fsqr-progress"' in ux_runtime_js
    assert 'className = "fsqr-toast-stack"' in ux_runtime_js
    assert 'className = "fsqr-offline-banner"' in ux_runtime_js

    tooltip_js = Path("static/tooltip.js").read_text(encoding="utf-8")
    assert 'TOOLTIP_CLASS = "fsqr-tooltip"' in tooltip_js
    assert "document.body.appendChild(tooltip)" in tooltip_js


def _split_top_level_commas(text: str) -> list[str]:
    """括弧の深さを見ながら最上位のカンマだけで分割する。"""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _extract_create_table_columns(sql_text: str, table_name: str) -> set[str]:
    """CREATE TABLE 定義から列名の集合を取り出す（INDEX/CONSTRAINT等は除外）。"""
    import re

    match = re.search(
        rf"CREATE TABLE {re.escape(table_name)} \((.*?)\)\s*ENGINE",
        sql_text,
        re.S,
    )
    assert match, f"CREATE TABLE {table_name} が見つかりません"
    skip_prefixes = {
        "INDEX",
        "UNIQUE",
        "CONSTRAINT",
        "PRIMARY",
        "KEY",
        "FOREIGN",
    }
    columns: set[str] = set()
    for part in _split_top_level_commas(match.group(1)):
        part = part.strip()
        if not part:
            continue
        first_word = part.split()[0]
        if first_word.upper() in skip_prefixes:
            continue
        columns.add(first_word)
    return columns


def test_task_item_schema_matches_fresh_install_and_migrations():
    """db_init/create_tables.sql（新規構築用）と alembic マイグレーション
    （既存環境への適用用）で task_item の列構成が一致することを確認する回帰テスト。

    feature/task-start-date で task_item.start_date を参照するコードが
    追加されたが、対応する alembic マイグレーションが作られなかったため、
    既存環境（先に task_item が作られていたルーム）では start_date 列が
    追加されず、GET /api/task/{room_id}/items が
    "Unknown column 'start_date'" で 500 を返し続けていた。
    このテストは同種の列不足を再発時に検知する。
    """
    import re
    from pathlib import Path

    create_tables_sql = Path("db_init/create_tables.sql").read_text(encoding="utf-8")
    fresh_install_columns = _extract_create_table_columns(
        create_tables_sql, "task_item"
    )

    versions_dir = Path("alembic/versions")
    version_files = sorted(versions_dir.glob("*.py"))
    assert version_files, "alembic のマイグレーションファイルが見つかりません"

    # 0010 が task_item を新規作成する唯一のマイグレーション
    task_service_migration = next(
        f for f in version_files if f.name.endswith("_task_service.py")
    )
    migrated_columns = _extract_create_table_columns(
        task_service_migration.read_text(encoding="utf-8"), "task_item"
    )

    # それ以降にtask_itemへ列を追加している全マイグレーションを反映する
    for version_file in version_files:
        content = version_file.read_text(encoding="utf-8")
        for match in re.finditer(r"ALTER TABLE task_item ADD COLUMN (\w+)", content):
            migrated_columns.add(match.group(1))

    missing = fresh_install_columns - migrated_columns
    assert not missing, (
        "db_init/create_tables.sql には存在するが、alembic マイグレーションを"
        f"順番に適用しても task_item に追加されない列があります: {missing}。"
        "新しいマイグレーション（例: alembic/versions/2xxxxxxx_xxxx_*.py）で"
        "ALTER TABLE task_item ADD COLUMN ... を追加してください。"
    )


def test_task_new_item_forms_default_dates_to_today():
    """新規タスク作成時、開始日・締切日の入力欄がデフォルトで今日の日付になる。

    - 編集ダイアログを新規作成モードで開く editor.js の openCreate() は、
      カレンダーから明示的な締切日が渡されなかった場合、開始日・締切日を
      クライアントのローカル日付（today）で初期化する。
    - 締切日が今日より前の日付で明示指定された場合（カレンダーで過去日を
      選んで追加した場合）は、開始日 > 締切日 のバリデーションエラーを
      避けるため開始日は空欄のままにする。
    - ボード上部のクイック追加フォーム（taskCreateForm）も、ページ読み込み時
      および追加成功後の入力欄リセット時に今日の日付を再セットする。
    既存の編集モード（open()）は item.start_date / item.due_date の値を
    そのまま使い続けており、既存タスクの値を上書きしないことも確認する。
    """
    from pathlib import Path

    editor_js = Path("static/js/task_board/editor.js").read_text(encoding="utf-8")
    main_js = Path("static/js/task_board/main.js").read_text(encoding="utf-8")

    # 1. openCreate() が今日の日付を既定値として計算していること
    assert "function openCreate(initialStatus, options) {" in editor_js
    assert "var todayStr = formatDate(new Date());" in editor_js
    assert "var dueDate = (options && options.dueDate) || todayStr;" in editor_js
    assert "var startDate = dueDate >= todayStr ? todayStr : '';" in editor_js
    assert "element('taskEditorStartDate').value = startDate;" in editor_js
    assert "element('taskEditorDueDate').value = dueDate;" in editor_js

    # 2. 編集モード（既存タスクを開く open()）は今まで通り item の値をそのまま使い、
    #    今日の日付で上書きしないこと（新規作成時のみのデフォルト値であることを保証）
    assert "element('taskEditorStartDate').value = item.start_date || '';" in editor_js
    assert "element('taskEditorDueDate').value = item.due_date || '';" in editor_js

    # 3. クイック追加フォームの日付欄も今日の日付を初期値・リセット値にすること
    assert "function quickAddDefaultDate() {" in main_js
    assert (
        "return modules.calendarLayout ? modules.calendarLayout.dateKey(new Date()) : '';"
        in main_js
    )
    assert "function initQuickAddDefaultDates() {" in main_js
    assert (
        "if (startDateInput && !startDateInput.value) startDateInput.value = todayStr;"
        in main_js
    )
    assert (
        "if (dueDateInput && !dueDateInput.value) dueDateInput.value = todayStr;"
        in main_js
    )
    assert "initQuickAddDefaultDates();" in main_js
    assert "var resetDate = quickAddDefaultDate();" in main_js
    assert "if (startDateInput) startDateInput.value = resetDate;" in main_js
    assert "if (dueDateInput) dueDateInput.value = resetDate;" in main_js


def test_task_board_page_renders_date_input_fields(test_client: TestClient):
    """タスクボードページに、開始日・締切日を入力する欄（クイック追加・編集ダイアログ双方）が
    今回の変更後も存在すること（回帰確認）。
    """
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
    assert 'id="taskCreateStartDate"' in body
    assert 'id="taskCreateDueDate"' in body
    assert 'id="taskEditorStartDate"' in body
    assert 'id="taskEditorDueDate"' in body


def test_task_quick_add_date_fields_share_one_grid(test_client: TestClient):
    """クイック追加の開始日・期限日が同じ幅になり、狭い画面で重ならないこと。

    以前は `.task-quick-add-controls` の `1fr auto` により片方だけが縮み、
    スマホでは日付テキストがカレンダーアイコンと重なって欠けていた。
    2 つの入力欄を等分グリッドへ入れ、狭い画面では 1 列へ落とすことで防ぐ。
    """
    from pathlib import Path

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

    # 1. 2 つの日付欄が同じグリッド（.task-quick-add-dates）に入り、
    #    それぞれ見出しつきの .task-date-field で包まれていること
    assert 'class="task-quick-add-dates"' in body
    assert body.count('class="task-date-field"') == 2
    assert body.count('class="task-date-field__label"') == 2
    for label in ("開始", "期限"):
        assert (
            f'<span class="task-date-field__label" aria-hidden="true">{label}</span>'
            in body
        )
    # 見出しは視覚用。読み上げ用の完全なラベルは aria-label 側に残す
    assert 'aria-label="開始日"' in body
    assert 'aria-label="期限日"' in body

    css_content = Path("static/css/16-task-board.css").read_text(encoding="utf-8")

    # 2. 既定は等分の 2 列。片方だけが縮むことがない
    assert ".task-quick-add-dates {" in css_content
    dates_rule = css_content.split(".task-quick-add-dates {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in dates_rule

    # 3. 入力欄はグリッド列にぴったり収める（固定幅のままだと溢れる）
    assert ".task-date-field .task-input {" in css_content
    input_rule = css_content.split(".task-date-field .task-input {", 1)[1].split(
        "}", 1
    )[0]
    assert "box-sizing: border-box;" in input_rule
    assert "width: 100%;" in input_rule

    # 4. 狭い画面（<=580px）では 1 列へ落として縦に積む
    narrow_block = css_content.split("@media (max-width: 580px) {", 1)[1]
    assert "grid-template-columns: minmax(0, 1fr);" in narrow_block


def test_task_calendar_layout_metrics_are_shared_variables():
    """カレンダーの寸法を CSS 変数へ集約し、文字とバーが重ならないこと。

    バーは日付セルの外（週行のオーバーレイ）に絶対配置されるため、
    「見出しの高さ」「列の間隔」がセル側とズレると、バーが日付の数字や
    「他N件」に重なる。3 レイヤーが同じ変数を参照することで防ぐ。
    """
    from pathlib import Path

    css_content = Path("static/css/16-task-board.css").read_text(encoding="utf-8")

    # 1. 寸法は .task-calendar に集約されていること
    calendar_rule = css_content.split(".task-calendar {", 1)[1].split("}", 1)[0]
    for variable in (
        "--task-cal-col-gap",
        "--task-cal-row-gap",
        "--task-cal-head-h",
        "--task-cal-lane-h",
        "--task-cal-lane-gap",
        "--task-cal-pad-bottom",
        "--task-cal-more-h",
    ):
        assert variable in calendar_rule, (
            f".task-calendar に {variable} の定義が見つかりません"
        )

    # 2. 曜日見出し・日付セル・バーのオーバーレイが同じ列間隔を使うこと
    #    （揃っていないと曜日ラベルが列の真上から左右にずれる）
    for selector in (
        ".task-calendar__weekdays {",
        ".task-calendar__week-cells {",
    ):
        rule = css_content.split(selector, 1)[1].split("}", 1)[0]
        assert "gap: var(--task-cal-col-gap);" in rule, (
            f"{selector} が --task-cal-col-gap を使っていません"
        )
    bars_rule = css_content.split(".task-calendar__bars {", 1)[1].split("}", 1)[0]
    assert "column-gap: var(--task-cal-col-gap);" in bars_rule
    # 3. バーの開始位置とセルの最低高さが同じ見出し高さを参照すること
    assert "top: var(--task-cal-head-h);" in bars_rule
    cell_rule = css_content.split(".task-calendar__cell {", 1)[1].split("}", 1)[0]
    assert "var(--task-cal-head-h)" in cell_rule
    # 4. 「他N件」を出す週はその 1 行分だけセルを高くすること
    assert "var(--task-cal-more, 0) *" in cell_rule
    assert "var(--task-cal-more-h)" in cell_rule

    calendar_js = Path("static/js/task_board/calendar.js").read_text(encoding="utf-8")
    assert "'--task-cal-more'" in calendar_js
    assert "hasMore" in calendar_js


def test_task_calendar_mobile_bars_keep_task_colors():
    """狭い画面でも期間バーがタスク固有色を保ち、日付の数字に被らないこと。

    以前はモバイル用の上書きが背景を --task-todo で塗り潰していたため、
    どの帯も同じ色になり見分けられなかった。
    """
    from pathlib import Path

    css_content = Path("static/css/16-task-board.css").read_text(encoding="utf-8")
    narrow_block = css_content.split("@media (max-width: 580px) {", 1)[1]

    # 1. モバイルでも --task-item-color（タスク固有色）で塗ること
    assert "background: var(--task-item-color, var(--task-todo));" in narrow_block
    # 2. 単色で塗り潰す旧実装（identity 色の破棄）へ戻っていないこと
    assert "background: var(--task-todo);" not in narrow_block
    # 3. 「今日」の丸バッジを縮め、見出し高さの内側に収めること
    assert ".task-calendar__cell.is-today .task-calendar__date {" in narrow_block
    assert "--task-cal-head-h: 1.8rem;" in narrow_block
