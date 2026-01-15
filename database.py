import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_scoped_session, async_sessionmaker, create_async_engine
from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as SATimeoutError

load_dotenv()

host = os.getenv("SQL_HOST")
user = os.getenv("SQL_USER")
pw = os.getenv("SQL_PW")
db = os.getenv("SQL_DB")

engine = create_async_engine(
    f"mysql+aiomysql://{user}:{pw}@{host}/{db}?charset=utf8mb4",
    pool_recycle=280,
    pool_size=10,
    pool_pre_ping=True,
    max_overflow=5,
    pool_timeout=10,
    echo=False,
)

async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
db_session = async_scoped_session(async_session_factory, scopefunc=asyncio.current_task)


async def remove_db_session():
    await db_session.remove()


def is_retryable_db_error(exc) -> bool:
    if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
        return True
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, SATimeoutError):
        return True
    orig = getattr(exc, "orig", None)
    if orig and getattr(orig, "args", None):
        code = orig.args[0]
        if code in (2006, 2013, 2014, 2055):
            return True
    message = str(exc).lower()
    return (
        "lost connection" in message
        or "server has gone away" in message
        or "connection reset by peer" in message
    )


async def reset_db_connection():
    try:
        await db_session.rollback()
    except Exception:
        pass
    try:
        await db_session.remove()
    except Exception:
        pass
    try:
        await engine.dispose()
    except Exception:
        pass
