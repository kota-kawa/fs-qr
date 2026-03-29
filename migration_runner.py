import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


BASE_DIR = Path(__file__).resolve().parent
ALEMBIC_INI_PATH = BASE_DIR / "alembic.ini"
MIGRATION_LOCK_KEY = 956341221


def _db_env() -> dict[str, str]:
    host = os.getenv("SQL_HOST")
    user = os.getenv("SQL_USER")
    pw = os.getenv("SQL_PW")
    db = os.getenv("SQL_DB")
    if not all([host, user, pw, db]):
        missing = [
            name
            for name, value in {
                "SQL_HOST": host,
                "SQL_USER": user,
                "SQL_PW": pw,
                "SQL_DB": db,
            }.items()
            if not value
        ]
        raise RuntimeError(
            f"Missing database env vars for migrations: {', '.join(missing)}"
        )
    return {"host": host, "user": user, "pw": pw, "db": db}


def _sync_url() -> str:
    env = _db_env()
    return (
        f"mysql+pymysql://{env['user']}:{env['pw']}@{env['host']}/"
        f"{env['db']}?charset=utf8mb4"
    )


def _async_url() -> str:
    env = _db_env()
    return (
        f"mysql+aiomysql://{env['user']}:{env['pw']}@{env['host']}/"
        f"{env['db']}?charset=utf8mb4"
    )


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI_PATH))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _sync_url())
    return cfg


async def run_migrations() -> None:
    if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "true").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    engine = create_async_engine(_async_url(), pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            lock_acquired = False
            lock_row = await conn.execute(
                text("SELECT GET_LOCK(:key, :timeout) AS got_lock"),
                {"key": str(MIGRATION_LOCK_KEY), "timeout": 30},
            )
            lock_value = lock_row.scalar()
            if int(lock_value or 0) != 1:
                raise RuntimeError("Failed to acquire migration lock")
            lock_acquired = True
            try:

                def _upgrade(sync_conn) -> None:
                    from alembic import command

                    cfg = _alembic_config()
                    cfg.attributes["connection"] = sync_conn
                    command.upgrade(cfg, "head")

                await conn.run_sync(_upgrade)
            finally:
                if lock_acquired:
                    await conn.execute(
                        text("SELECT RELEASE_LOCK(:key)"),
                        {"key": str(MIGRATION_LOCK_KEY)},
                    )
    finally:
        await engine.dispose()
