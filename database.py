import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

load_dotenv()

host = os.getenv("SQL_HOST")
user = os.getenv("SQL_USER")
pw = os.getenv("SQL_PW")
db = os.getenv("SQL_DB")

engine = create_engine(
    f"mysql+pymysql://{user}:{pw}@{host}/{db}?charset=utf8mb4",
    pool_recycle=280,
    pool_size=10,
    pool_pre_ping=True,
    max_overflow=5,
    echo=False,
)

db_session = scoped_session(sessionmaker(bind=engine))


def remove_db_session():
    db_session.remove()
