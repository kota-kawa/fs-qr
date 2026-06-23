import importlib
from unittest.mock import patch

import pytest


def run(coro):
    import asyncio

    return asyncio.run(coro)


def test_gunicorn_conf_reads_environment_with_safe_defaults(monkeypatch):
    import gunicorn_conf

    try:
        monkeypatch.setenv("WEB_CONCURRENCY", "8")
        monkeypatch.setenv("GUNICORN_MAX_REQUESTS", "0")
        monkeypatch.setenv("GUNICORN_MAX_REQUESTS_JITTER", "25")
        monkeypatch.setenv("GUNICORN_TIMEOUT", "120")
        monkeypatch.setenv("GUNICORN_GRACEFUL_TIMEOUT", "20")
        monkeypatch.setenv("GUNICORN_KEEPALIVE", "3")
        monkeypatch.setenv("GUNICORN_ACCESS_LOG", "-")
        monkeypatch.setenv("GUNICORN_ERROR_LOG", "-")
        importlib.reload(gunicorn_conf)

        assert gunicorn_conf.workers == 8
        assert gunicorn_conf.max_requests == 0
        assert gunicorn_conf.max_requests_jitter == 25
        assert gunicorn_conf.timeout == 120
        assert gunicorn_conf.graceful_timeout == 20
        assert gunicorn_conf.keepalive == 3
        assert gunicorn_conf.accesslog == "-"
        assert gunicorn_conf.errorlog == "-"

        monkeypatch.setenv("WEB_CONCURRENCY", "0")
        monkeypatch.setenv("GUNICORN_TIMEOUT", "invalid")
        importlib.reload(gunicorn_conf)

        assert gunicorn_conf.workers == 4
        assert gunicorn_conf.timeout == 360
    finally:
        importlib.reload(gunicorn_conf)


def test_migration_runner_env_urls_and_disabled_startup(monkeypatch):
    import migration_runner

    for name in ("SQL_HOST", "SQL_USER", "SQL_PW", "SQL_DB"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="SQL_HOST, SQL_USER, SQL_PW, SQL_DB"):
        migration_runner._db_env()

    monkeypatch.setenv("SQL_HOST", "db.example")
    monkeypatch.setenv("SQL_USER", "app")
    monkeypatch.setenv("SQL_PW", "secret")
    monkeypatch.setenv("SQL_DB", "fsqr")
    assert migration_runner._sync_url() == (
        "mysql+pymysql://app:secret@db.example/fsqr?charset=utf8mb4"
    )
    assert migration_runner._async_url() == (
        "mysql+aiomysql://app:secret@db.example/fsqr?charset=utf8mb4"
    )

    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "off")
    with patch("migration_runner.create_async_engine") as create_engine:
        run(migration_runner.run_migrations())
        create_engine.assert_not_called()


class FakeScalarRow:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class FakeMigrationConnection:
    def __init__(self, lock_value):
        self.lock_value = lock_value
        self.executed = []
        self.synced = False

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        if "GET_LOCK" in str(statement):
            return FakeScalarRow(self.lock_value)
        return FakeScalarRow(1)

    async def run_sync(self, upgrade):
        self.synced = True


class FakeEngineBegin:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeMigrationEngine:
    def __init__(self, connection):
        self.connection = connection
        self.disposed = False

    def begin(self):
        return FakeEngineBegin(self.connection)

    async def dispose(self):
        self.disposed = True


def test_migration_runner_runs_under_database_lock(monkeypatch):
    import migration_runner

    monkeypatch.setenv("SQL_HOST", "db.example")
    monkeypatch.setenv("SQL_USER", "app")
    monkeypatch.setenv("SQL_PW", "secret")
    monkeypatch.setenv("SQL_DB", "fsqr")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")

    connection = FakeMigrationConnection(lock_value=1)
    engine = FakeMigrationEngine(connection)

    with patch("migration_runner.create_async_engine", return_value=engine):
        run(migration_runner.run_migrations())

    assert connection.synced is True
    assert any("GET_LOCK" in statement for statement, _ in connection.executed)
    assert any("RELEASE_LOCK" in statement for statement, _ in connection.executed)
    assert engine.disposed is True


def test_migration_runner_disposes_engine_when_lock_fails(monkeypatch):
    import migration_runner

    monkeypatch.setenv("SQL_HOST", "db.example")
    monkeypatch.setenv("SQL_USER", "app")
    monkeypatch.setenv("SQL_PW", "secret")
    monkeypatch.setenv("SQL_DB", "fsqr")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "yes")

    connection = FakeMigrationConnection(lock_value=0)
    engine = FakeMigrationEngine(connection)

    with patch("migration_runner.create_async_engine", return_value=engine):
        with pytest.raises(RuntimeError, match="migration lock"):
            run(migration_runner.run_migrations())

    assert connection.synced is False
    assert not any("RELEASE_LOCK" in statement for statement, _ in connection.executed)
    assert engine.disposed is True
