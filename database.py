import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_scoped_session, async_sessionmaker, create_async_engine

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
    echo=False,
)

async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
db_session = async_scoped_session(async_session_factory, scopefunc=asyncio.current_task)


async def remove_db_session():
    await db_session.remove()
