import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def run(coro):
    return asyncio.run(coro)


def test_fsqr_data_save_lookup_remove_and_expiration(tmp_path):
    import FSQR.fsqr_data as fd
    from password_security import hash_password

    hashed = hash_password("pw123")
    data_rows = [{"secure_id": "secure1", "password": hashed, "file_type": "single"}]
    calls = []

    async def execute(query, params=None, fetch=False):
        calls.append((str(query), params or {}, fetch))
        if fetch and "WHERE id" in str(query):
            return data_rows
        if fetch and "WHERE secure_id" in str(query):
            return data_rows
        if fetch and "expires_at <= NOW" in str(query):
            return [{"secure_id": "secure1"}]
        if fetch:
            return [{"secure_id": "secure1"}, {"secure_id": ""}]
        return None

    async def scenario():
        file_path = tmp_path / "secure1.enc"
        file_path.write_bytes(b"encrypted")

        with (
            patch("FSQR.fsqr_data.STATIC", str(tmp_path)),
            patch("FSQR.fsqr_data.execute_query", new=execute),
            patch("FSQR.fsqr_data.invalidate_cache_entry", new=AsyncMock()),
            patch("FSQR.fsqr_data.invalidate_cache_prefix", new=AsyncMock()),
            patch("share_links.revoke_resource_links", new=AsyncMock()) as revoke,
            patch("FSQR.fsqr_data.record_expiration_cleanup_status", new=AsyncMock()),
        ):
            await fd.save_file(
                "uuid1",
                "room1",
                "pw123",
                "secure1",
                file_type="single",
                original_filename="report.txt",
                retention_hours=6,
                share_token="share-token",
            )

            assert await fd.try_login.__wrapped__("room1", "pw123") == "secure1"
            assert await fd.try_login.__wrapped__("room1", "bad") is None
            assert await fd.get_data_by_credentials.__wrapped__("room1", "pw123") == [
                data_rows[0]
            ]
            assert await fd.get_data_by_credentials.__wrapped__("room1", "bad") == []
            assert await fd.get_data_by_share_token.__wrapped__("share-token") == [
                {"secure_id": "secure1"},
                {"secure_id": ""},
            ]

            await fd.remove_data("secure1")
            assert not file_path.exists()
            revoke.assert_awaited()

            stats = await fd.remove_expired_files()
            assert stats["checked"] == 1
            assert stats["removed"] == 1

    run(scenario())
    assert any("INSERT INTO fsqr" in query for query, _, _ in calls)
    assert any(
        "password_lookup_hash" in query and "WHERE id" in query
        for query, _, fetch in calls
        if fetch
    )
    assert any("DELETE FROM fsqr" in query for query, _, _ in calls)


def test_group_data_room_lifecycle_and_expiration(tmp_path):
    import Group.group_data as gd
    from password_security import hash_password

    hashed = hash_password("123456")
    calls = []

    async def execute(query, params=None, fetch=False):
        calls.append((str(query), params or {}, fetch))
        if fetch and "SELECT room_id, password" in str(query):
            return [{"room_id": "roomA", "password": hashed}]
        if fetch and "WHERE room_id" in str(query):
            return [{"room_id": "roomA", "password": hashed}]
        if fetch and "expires_at <= NOW" in str(query):
            return [{"room_id": "roomA"}, {"room_id": ""}]
        if fetch:
            return [{"room_id": "roomA"}, {"room_id": "roomB"}]
        return None

    async def scenario():
        current_folder = tmp_path / "current" / "roomA"
        legacy_folder = tmp_path / "legacy" / "roomA"
        current_folder.mkdir(parents=True)
        legacy_folder.mkdir(parents=True)

        with (
            patch("Group.group_data.execute_query", new=execute),
            patch("Group.group_data.invalidate_cache_entry", new=AsyncMock()),
            patch("Group.group_data.invalidate_cache_prefix", new=AsyncMock()),
            patch("Group.group_data.iter_room_folders") as folders,
            patch("Group.group_data.group_ws_hub.close_room", new=AsyncMock()),
            patch("share_links.revoke_resource_links", new=AsyncMock()),
        ):
            folders.return_value = (
                ("current", str(current_folder)),
                ("legacy", str(legacy_folder)),
            )

            await gd.create_room("public", "123456", "roomA", retention_hours=6)
            assert await gd.pich_room_id_direct("public", "123456") == "roomA"
            assert await gd.pich_room_id_direct("public", "bad") is None
            assert await gd.get_data_by_room_credentials("roomA", "123456")
            assert await gd.get_data_by_room_credentials("roomA", "bad") is None

            assert await gd.remove_data("roomA") is True
            assert not current_folder.exists()
            assert not legacy_folder.exists()

            await gd.remove_expired_rooms()

    run(scenario())
    assert any("INSERT INTO room" in query for query, _, _ in calls)
    assert any("DELETE FROM room" in query for query, _, _ in calls)


def test_group_data_remove_data_keeps_record_when_delete_fails(tmp_path):
    import Group.group_data as gd

    async def execute(query, params=None, fetch=False):
        if fetch:
            return [{"room_id": "roomA"}]
        return None

    async def scenario():
        room_folder = tmp_path / "roomA"
        room_folder.mkdir()
        with (
            patch("Group.group_data.execute_query", new=execute),
            patch(
                "Group.group_data.iter_room_folders",
                return_value=(("current", str(room_folder)),),
            ),
            patch("Group.group_data.shutil.rmtree", side_effect=OSError("denied")),
        ):
            assert await gd.remove_data("roomA") is False

    run(scenario())


def test_task_data_room_item_and_expiration_lifecycle():
    """Task はルーム作成、カード作成、期限切れ削除を生SQL層で完結する。"""
    import Task.task_data as td
    from password_security import hash_password

    hashed = hash_password("123456")
    calls = []

    class Result:
        lastrowid = 12

        def mappings(self):
            return self

        def first(self):
            return {"last_position": 0}

    class TaskDbSession:
        def begin(self):
            return FakeBegin()

        async def execute(self, query, params):
            calls.append((str(query), params))
            return Result()

    async def execute(query, params=None, fetch=False):
        query_text = str(query)
        calls.append((query_text, params or {}, fetch))
        if fetch and "SELECT room_id, password" in query_text:
            return [{"room_id": "taskA", "password": hashed}]
        if fetch and "FROM task_room WHERE room_id" in query_text:
            return [
                {
                    "room_id": "taskA",
                    "id": "public",
                    "password": hashed,
                    "retention_hours": 24,
                    "status": "active",
                }
            ]
        if fetch and "FROM task_item WHERE room_id" in query_text:
            return [
                {
                    "item_id": 12,
                    "title": "task",
                    "note": "",
                    "board_status": "todo",
                    "priority": "normal",
                    "due_date": None,
                    "position": 100,
                    "version": 0,
                    "created_at": None,
                    "updated_at": None,
                }
            ]
        if fetch and "expires_at <= NOW" in query_text:
            return [{"room_id": "taskA"}]
        return None

    async def scenario():
        with (
            patch("Task.task_data.execute_query", new=execute),
            patch("Task.task_data.db_session", TaskDbSession()),
            patch("Task.task_data.invalidate_cache_prefix", new=AsyncMock()),
            patch("share_links.revoke_resource_links", new=AsyncMock()) as revoke,
        ):
            await td.create_room("public", "123456", "taskA", retention_hours=24)
            assert await td.pick_room_id_direct("public", "123456") == "taskA"
            assert await td.get_room_meta_direct("taskA", "123456")
            item = await td.create_item(
                "taskA",
                {
                    "title": "task",
                    "note": "",
                    "board_status": "todo",
                    "priority": "normal",
                    "tag_ids": [],
                    "due_date": None,
                },
            )
            assert item and item["item_id"] == 12
            assert await td.remove_expired_rooms() == ["taskA"]
            revoke.assert_awaited_once()

    run(scenario())
    assert any("INSERT INTO task_room" in query for query, *_ in calls)
    assert any("INSERT INTO task_item" in query for query, *_ in calls)
    assert any("UPDATE task_room SET status" in query for query, *_ in calls)


def test_task_data_update_rejects_partial_date_range_atomically():
    """開始日・期限日の片側更新で逆転した値を保存しない。"""
    import Task.task_data as td

    calls = []

    class Result:
        def mappings(self):
            return self

        def first(self):
            return {
                "item_id": 12,
                "title": "task",
                "note": "",
                "board_status": "todo",
                "priority": "normal",
                "start_date": "2026-08-20",
                "due_date": "2026-08-25",
                "position": 100,
                "version": 0,
                "created_at": None,
                "updated_at": None,
            }

    class TaskDbSession:
        def begin(self):
            return FakeBegin()

        async def execute(self, query, params):
            calls.append(str(query))
            return Result()

    async def scenario():
        with patch("Task.task_data.db_session", TaskDbSession()):
            await td.update_item("taskA", 12, {"due_date": "2026-08-15"}, version=0)

    import pytest

    with pytest.raises(td.InvalidTaskDateRange):
        run(scenario())
    assert len(calls) == 1
    assert not any("UPDATE task_item SET" in query for query in calls)


def test_task_data_create_rechecks_room_limit_inside_transaction():
    """同時追加で事前の件数確認をすり抜けても上限を超えない。"""
    import Task.task_data as td
    import pytest

    calls = []

    class Result:
        def __init__(self, row):
            self.row = row

        def mappings(self):
            return self

        def first(self):
            return self.row

    class TaskDbSession:
        def begin(self):
            return FakeBegin()

        async def execute(self, query, params):
            calls.append(str(query))
            return Result({"room_id": "taskA"} if len(calls) == 1 else {"count": 200})

    async def scenario():
        with patch("Task.task_data.db_session", TaskDbSession()):
            await td.create_item(
                "taskA",
                {
                    "title": "task",
                    "note": "",
                    "board_status": "todo",
                    "priority": "normal",
                    "tag_ids": [],
                    "due_date": None,
                },
                max_items=200,
            )

    with pytest.raises(td.TaskItemLimitReached):
        run(scenario())
    assert len(calls) == 2
    assert not any("INSERT INTO task_item" in query for query in calls)


class FakeBegin:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeDbSession:
    def __init__(self):
        self.execute = AsyncMock()

    def begin(self):
        return FakeBegin()


def test_note_data_tables_meta_content_and_cleanup():
    import Note.note_data as nd
    from password_security import hash_password

    hashed = hash_password("note-pw")
    calls = []

    async def execute(query, params=None, fetch=False):
        query_text = str(query)
        calls.append((query_text, params or {}, fetch))
        if fetch and "information_schema" in query_text:
            return [{"cnt": 0}]
        if (
            fetch
            and "FROM note_room" in query_text
            and "share_token_hash" in query_text
        ):
            return [{"room_id": "note1", "id": "public"}]
        if fetch and "SELECT room_id, id, password" in query_text:
            return [{"room_id": "note1", "id": "public", "password": hashed}]
        if fetch and "SELECT room_id, password" in query_text:
            return [{"room_id": "note1", "password": hashed}]
        if fetch and "FROM note_content" in query_text:
            return [{"room_id": "note1", "content": "hello", "version": 2}]
        if fetch and "expires_at <= NOW" in query_text:
            return [{"room_id": "note1"}]
        if fetch:
            return []
        return 1

    async def scenario():
        db_session = FakeDbSession()
        with (
            patch("Note.note_data.execute_query", new=execute),
            patch("Note.note_data.db_session", db_session),
            patch("Note.note_data.invalidate_cache_entry", new=AsyncMock()),
            patch("Note.note_data.invalidate_cache_prefix", new=AsyncMock()),
            patch("share_links.revoke_resource_links", new=AsyncMock()),
        ):
            await nd.ensure_index(
                "note_room", "idx", "ALTER TABLE note_room ADD INDEX idx (id)"
            )
            await nd.ensure_unique_key(
                "note_room",
                "uq",
                "ALTER TABLE note_room ADD UNIQUE KEY uq (room_id)",
            )
            await nd.ensure_column(
                "note_room",
                "deleted_at",
                "ALTER TABLE note_room ADD COLUMN deleted_at DATETIME",
            )
            await nd.ensure_tables()
            await nd.create_room("public", "note-pw", "note1", share_token_hash="hash")

            room_meta = await nd.get_room_meta_direct("note1")
            assert room_meta["room_id"] == "note1"
            assert await nd.get_room_meta_direct("note1", password="note-pw")
            assert await nd.get_room_meta_direct("note1", password="bad") is None
            shared_meta = await nd.get_room_meta_by_share_token_hash("hash")
            assert shared_meta["room_id"] == "note1"
            assert await nd.pick_room_id_direct("public", "note-pw") == "note1"
            assert await nd.pick_room_id_direct("public", "bad") is None
            row = await nd.get_row("note1")
            assert row["content"] == "hello"
            assert await nd.save_content("note1", "updated", expected_version=2) == 1

            await nd.remove_room("note1")
            result = await nd.remove_expired_rooms()
            assert result["expired_count"] == 1
            assert result["expired_room_ids"] == ["note1"]

    run(scenario())
    assert any("CREATE TABLE IF NOT EXISTS note_room" in query for query, _, _ in calls)
    assert any("UPDATE note_room" in query for query, _, _ in calls)


def test_scheduler_exclusive_job_lock_paths():
    import scheduler

    skipped_lock = MagicMock()
    skipped_lock.acquire.return_value = False
    skipped_redis = MagicMock()
    skipped_redis.lock.return_value = skipped_lock

    def skipped_job():
        raise AssertionError("job should not run without the lock")

    with patch.object(scheduler, "r_lock", skipped_redis):
        wrapped = scheduler.exclusive_job(skipped_job)
        assert wrapped() is None
        skipped_redis.lock.assert_called_once_with(
            "scheduler:lock:skipped_job", timeout=3600, blocking=False
        )
        skipped_lock.release.assert_not_called()

    acquired_lock = MagicMock()
    acquired_lock.acquire.return_value = True
    acquired_lock.release.side_effect = RuntimeError("expired")
    acquired_redis = MagicMock()
    acquired_redis.lock.return_value = acquired_lock

    def job(value):
        return value + 1

    with (
        patch.object(scheduler, "r_lock", acquired_redis),
        patch.object(scheduler.redis, "LockError", RuntimeError, create=True),
    ):
        assert scheduler.exclusive_job(job)(2) == 3
        acquired_redis.lock.assert_called_once_with(
            "scheduler:lock:job", timeout=3600, blocking=False
        )
        acquired_lock.release.assert_called_once()


def test_scheduler_expiration_jobs_reset_connections_and_notify_notes():
    import scheduler

    async def scenario():
        with (
            patch(
                "scheduler.fsqr_data.remove_expired_files", new=AsyncMock()
            ) as remove_fsqr,
            patch("scheduler.reset_db_connection", new=AsyncMock()) as reset_db,
        ):
            await scheduler._remove_expired_fsqr_async()
            remove_fsqr.assert_awaited_once()
            reset_db.assert_awaited_once()

        with (
            patch(
                "scheduler.group_data.remove_expired_rooms", new=AsyncMock()
            ) as remove_group,
            patch("scheduler.reset_db_connection", new=AsyncMock()) as reset_db,
        ):
            await scheduler._remove_expired_group_rooms_async()
            remove_group.assert_awaited_once()
            reset_db.assert_awaited_once()

        with (
            patch(
                "scheduler.note_data.remove_expired_rooms",
                new=AsyncMock(return_value={"expired_room_ids": ["note1", "note2"]}),
            ) as remove_notes,
            patch("scheduler.publish_room_expired", new=AsyncMock()) as publish,
            patch("scheduler.reset_db_connection", new=AsyncMock()) as reset_db,
        ):
            await scheduler._remove_expired_note_rooms_async()
            remove_notes.assert_awaited_once()
            publish.assert_any_await("note1")
            publish.assert_any_await("note2")
            assert publish.await_count == 2
            reset_db.assert_awaited_once()

        with (
            patch(
                "scheduler.task_data.remove_expired_rooms", new=AsyncMock()
            ) as remove_tasks,
            patch("scheduler.reset_db_connection", new=AsyncMock()) as reset_db,
        ):
            await scheduler._remove_expired_task_rooms_async()
            remove_tasks.assert_awaited_once()
            reset_db.assert_awaited_once()

    run(scenario())


def test_scheduler_run_scheduler_registers_jobs_with_redis_store():
    import scheduler

    jobstores = []
    schedulers = []

    class FakeRedisJobStore:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            jobstores.append(self)

    class FakeBlockingScheduler:
        def __init__(self, jobstores):
            self.jobstores = jobstores
            self.jobs = []
            schedulers.append(self)

        def add_job(self, func, trigger, minutes, id, replace_existing):
            self.jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "minutes": minutes,
                    "id": id,
                    "replace_existing": replace_existing,
                }
            )

        def start(self):
            raise KeyboardInterrupt

    with (
        patch("scheduler.run_migrations", new=AsyncMock()) as run_migrations,
        patch("scheduler.RedisJobStore", FakeRedisJobStore),
        patch("scheduler.BlockingScheduler", FakeBlockingScheduler),
        patch("scheduler.REDIS_URL", "redis://:secret@example.test:6380/2"),
    ):
        scheduler.run_scheduler()

    run_migrations.assert_awaited_once()
    assert jobstores[0].kwargs == {
        "host": "example.test",
        "port": 6380,
        "db": 2,
        "password": "secret",
    }
    assert schedulers[0].jobstores == {"default": jobstores[0]}
    assert [job["id"] for job in schedulers[0].jobs] == [
        "remove_expired_fsqr",
        "remove_expired_group_rooms",
        "remove_expired_note_rooms",
        "remove_expired_task_rooms",
    ]
    assert all(job["replace_existing"] for job in schedulers[0].jobs)
    assert all(job["minutes"] == 5 for job in schedulers[0].jobs)


def test_task_data_tags_are_room_scoped_and_reusable():
    """タグはルーム単位で追加・解決でき、同名なら既存タグを返す。"""
    import Task.task_data as td

    calls = []
    existing = {"tag_id": 5, "name": "デザイン"}

    class Result:
        lastrowid = 9

        def __init__(self, row):
            self.row = row

        def mappings(self):
            return self

        def first(self):
            return self.row

    class TaskDbSession:
        def begin(self):
            return FakeBegin()

        async def execute(self, query, params):
            query_text = str(query)
            calls.append(query_text)
            if "SELECT tag_id, name FROM task_tag" in query_text:
                return Result(existing if params["name"] == "デザイン" else None)
            if "COUNT(*) AS count FROM task_tag" in query_text:
                return Result({"count": 1})
            return Result(None)

    async def scenario():
        with patch("Task.task_data.db_session", TaskDbSession()):
            # 同名タグは作り直さず、既存のタグをそのまま返す
            assert await td.create_tag("taskA", "デザイン") == existing
            created = await td.create_tag("taskA", "調査", max_tags=50)
            assert created == {"tag_id": 9, "name": "調査"}
            # 名前からの解決は、無いものだけを追加して ID の一覧を返す
            assert await td.resolve_tag_names("taskA", ["デザイン", "調査"]) == [5, 9]

    run(scenario())
    assert any("INSERT INTO task_tag" in query for query in calls)


def test_task_data_create_tag_stops_at_room_limit():
    """ルームのタグ上限に達したら追加しない。"""
    import Task.task_data as td
    import pytest

    calls = []

    class Result:
        lastrowid = 9

        def __init__(self, row):
            self.row = row

        def mappings(self):
            return self

        def first(self):
            return self.row

    class TaskDbSession:
        def begin(self):
            return FakeBegin()

        async def execute(self, query, params):
            query_text = str(query)
            calls.append(query_text)
            if "SELECT tag_id, name FROM task_tag" in query_text:
                return Result(None)
            if "COUNT(*) AS count FROM task_tag" in query_text:
                return Result({"count": 50})
            return Result(None)

    async def scenario():
        with patch("Task.task_data.db_session", TaskDbSession()):
            await td.create_tag("taskA", "調査", max_tags=50)

    with pytest.raises(td.TaskTagLimitReached):
        run(scenario())
    assert not any("INSERT INTO task_tag" in query for query in calls)


def test_task_data_replace_item_tags_filters_by_room():
    """タグの張り替えは、そのルームのタグに限定した INSERT ... SELECT で行う。"""
    import Task.task_data as td

    calls = []

    class TaskDbSession:
        async def execute(self, query, params):
            calls.append((str(query), params))

    async def scenario():
        with patch("Task.task_data.db_session", TaskDbSession()):
            await td._replace_item_tags("taskA", 12, [5, 9])

    run(scenario())

    delete_query, delete_params = calls[0]
    assert "DELETE FROM task_item_tag" in delete_query
    assert delete_params == {"item_id": 12}

    insert_query, insert_params = calls[1]
    assert "INSERT INTO task_item_tag" in insert_query
    # 他ルームのタグ ID を渡されても room_id 条件で弾かれる
    assert "WHERE room_id = :room_id" in insert_query
    assert insert_params["room_id"] == "taskA"
    assert insert_params["tag_0"] == 5
    assert insert_params["tag_1"] == 9


def test_task_data_update_item_bumps_version_for_tag_only_change():
    """タグだけの変更でも version を進め、他画面との競合検知を効かせる。"""
    import Task.task_data as td

    calls = []

    class Result:
        def mappings(self):
            return self

        def first(self):
            return {
                "item_id": 12,
                "title": "task",
                "note": "",
                "board_status": "todo",
                "priority": "normal",
                "start_date": None,
                "due_date": None,
                "position": 100,
                "version": 0,
                "created_at": None,
                "updated_at": None,
            }

    class TaskDbSession:
        def begin(self):
            return FakeBegin()

        async def execute(self, query, params):
            calls.append(str(query))
            return Result()

    async def scenario():
        with (
            patch("Task.task_data.db_session", TaskDbSession()),
            patch(
                "Task.task_data.get_item", new=AsyncMock(return_value={"item_id": 12})
            ),
        ):
            return await td.update_item("taskA", 12, {"tag_ids": [5]}, version=0)

    item, updated = run(scenario())
    assert updated is True
    assert any("UPDATE task_item SET" in query for query in calls)
    assert any("INSERT INTO task_item_tag" in query for query in calls)


def test_task_data_update_item_returns_tags_on_version_conflict():
    """競合で更新を拒否するときも、返す現在値にタグを添える。"""
    import Task.task_data as td

    class Result:
        def mappings(self):
            return self

        def first(self):
            return {
                "item_id": 12,
                "title": "task",
                "note": "",
                "board_status": "todo",
                "priority": "normal",
                "start_date": None,
                "due_date": None,
                "position": 100,
                "version": 3,
                "created_at": None,
                "updated_at": None,
            }

    calls = []

    class TaskDbSession:
        def begin(self):
            return FakeBegin()

        async def execute(self, query, params):
            calls.append(str(query))
            return Result()

    async def execute(query, params=None, fetch=False):
        if fetch and "FROM task_item_tag" in str(query):
            return [{"item_id": 12, "tag_id": 5, "name": "デザイン"}]
        return None

    async def scenario():
        with (
            patch("Task.task_data.db_session", TaskDbSession()),
            patch("Task.task_data.execute_query", new=execute),
        ):
            return await td.update_item("taskA", 12, {"title": "新しい題名"}, version=0)

    item, updated = run(scenario())
    assert updated is False
    assert item["version"] == 3
    assert item["tags"] == [{"tag_id": 5, "name": "デザイン"}]
    # 競合時は UPDATE を実行しない
    assert not any("UPDATE task_item SET" in query for query in calls)
