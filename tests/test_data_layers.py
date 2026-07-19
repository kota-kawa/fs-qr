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


class FakeRedisPipeline:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def sadd(self, *args):
        self.calls.append(("sadd", args))

    def expire(self, *args):
        self.calls.append(("expire", args))

    def srem(self, *args):
        self.calls.append(("srem", args))

    def scard(self, *args):
        self.calls.append(("scard", args))

    def delete(self, *args):
        self.calls.append(("delete", args))

    async def execute(self):
        return self.result


class FakeRedisClient:
    def __init__(self, member):
        self.member = member
        self.published = []
        self.deleted = []
        self.closed = False

    async def ping(self):
        return True

    def pipeline(self, transaction=True):
        return FakeRedisPipeline([1, 1, 0, 0])

    async def publish(self, channel, payload):
        self.published.append((channel, payload))
        return 1

    async def delete(self, key):
        self.deleted.append(key)

    async def smembers(self, key):
        return {self.member}

    async def scard(self, key):
        return 0

    async def close(self):
        self.closed = True


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


def test_note_realtime_publish_shutdown_and_pubsub_paths():
    import Note.note_realtime as nr

    async def scenario():
        client = FakeRedisClient(nr._connection_member("room1", "conn1"))
        with patch("Note.note_realtime.redis.from_url", return_value=client):
            nr._redis_client = None
            nr._pubsub_task = None
            assert await nr.get_redis() is client
            assert await nr.publish_room_update("room1", {"type": "note_updated"})
            assert await nr.publish_room_expired("room1")

        assert nr._decode_channel_room_id(b"note:room:abc") == "abc"
        assert nr._decode_channel_room_id("other") is None
        assert nr._parse_connection_member(b"inst:room:conn") == (
            "inst",
            "room",
            "conn",
        )
        assert nr._parse_connection_member("bad") == (None, None, None)

        hub = nr.RoomHub()
        ws = MagicMock()
        ws.close = AsyncMock(side_effect=RuntimeError("closed"))
        hub._rooms = {"room1": {ws: "conn1"}}
        await hub.close_room("room1")

        with patch("Note.note_realtime.get_redis", new=AsyncMock(return_value=client)):
            await hub._clear_instance_connections()

        nr._redis_client = client
        nr._pubsub_task = None
        await nr.shutdown()
        assert client.closed is True

    run(scenario())


def test_note_realtime_pubsub_loop_filters_and_dispatches_messages():
    import json

    import Note.note_realtime as nr

    class FakePubSub:
        def __init__(self, messages):
            self.messages = messages
            self.subscriptions = []
            self.closed = False

        async def psubscribe(self, pattern):
            self.subscriptions.append(pattern)

        def listen(self):
            return self._listen()

        async def _listen(self):
            for message in self.messages:
                yield message

        async def close(self):
            self.closed = True
            raise RuntimeError("close failed")

    async def scenario():
        messages = [
            None,
            {"type": "subscribe", "data": "ignored"},
            {"type": "message"},
            {"type": "message", "data": "not json"},
            {
                "type": "message",
                "data": json.dumps(
                    {
                        "room_id": "room1",
                        "payload": {"type": "note_updated"},
                        "source": nr.INSTANCE_ID,
                    }
                ),
            },
            {
                "type": "message",
                "data": json.dumps(
                    {
                        "room_id": "room1",
                        "payload": {"type": "note_updated", "content": "hello"},
                        "source": "other-instance",
                    }
                ),
            },
            {
                "type": "pmessage",
                "channel": b"note:room:room2",
                "data": json.dumps(
                    {
                        "payload": {"type": "room_expired"},
                        "source": "other-instance",
                    }
                ),
            },
            {
                "type": "message",
                "data": json.dumps(
                    {
                        "room_id": "room3",
                        "payload": None,
                        "source": "other-instance",
                    }
                ),
            },
        ]
        pubsub = FakePubSub(messages)
        client = MagicMock()
        client.pubsub.return_value = pubsub

        with (
            patch("Note.note_realtime.get_redis", new=AsyncMock(return_value=client)),
            patch.object(nr.hub, "broadcast", new=AsyncMock()) as broadcast,
            patch.object(nr.hub, "close_room", new=AsyncMock()) as close_room,
        ):
            await nr._pubsub_loop()

        assert pubsub.subscriptions == ["note:room:*"]
        assert pubsub.closed is True
        broadcast.assert_any_await(
            "room1", {"type": "note_updated", "content": "hello"}
        )
        broadcast.assert_any_await("room2", {"type": "room_expired"})
        assert broadcast.await_count == 2
        close_room.assert_awaited_once_with("room2")

    run(scenario())


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
    ]
    assert all(job["replace_existing"] for job in schedulers[0].jobs)
    assert all(job["minutes"] == 5 for job in schedulers[0].jobs)
