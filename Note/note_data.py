import os, logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

load_dotenv()
host = os.getenv("SQL_HOST")
user = os.getenv("SQL_USER")
pw   = os.getenv("SQL_PW")
db   = os.getenv("SQL_DB")

engine = create_engine(
    f"mysql+pymysql://{user}:{pw}@{host}/{db}?charset=utf8mb4",
    pool_recycle=280, pool_size=10, pool_pre_ping=True, max_overflow=5)

_session = scoped_session(sessionmaker(bind=engine))

# ────────────────────────────────────────────
CREATE_NOTE_ROOM = """
CREATE TABLE IF NOT EXISTS note_room(
  suji INT AUTO_INCREMENT PRIMARY KEY,
  time DATETIME NOT NULL,
  id VARCHAR(255) NOT NULL,
  password VARCHAR(255) NOT NULL,
  room_id VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

CREATE_NOTE_CONTENT = """
CREATE TABLE IF NOT EXISTS note_content(
  room_id VARCHAR(255) PRIMARY KEY,
  content LONGTEXT,
  updated_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

def _exec(q, params=None, fetch=False):
    try:
        res = _session.execute(text(q), params or {})
        if fetch:
            return [r._mapping for r in res]
        _session.commit()
    except Exception as e:
        _session.rollback()
        raise

def _ensure_tables():
    _exec(CREATE_NOTE_ROOM)
    _exec(CREATE_NOTE_CONTENT)
    log.info("note tables checked/created")

_ensure_tables()   # ← ★アプリ import 時に必ず実行★

# ────────────────────────────────────────────
def create_room(id_, password, room_id):
    _exec("""INSERT INTO note_room(time,id,password,room_id)
             VALUES(NOW(),:i,:p,:r)""",
          {"i": id_, "p": password, "r": room_id})

def pick_room_id(id_, password):
    rows = _exec("""SELECT room_id FROM note_room
                    WHERE id=:i AND password=:p""",
                 {"i": id_, "p": password}, fetch=True)
    return rows[0]["room_id"] if rows else False

def get_row(room_id):
    rows = _exec("SELECT * FROM note_content WHERE room_id=:r",
                 {"r": room_id}, fetch=True)
    if rows:
        return rows[0]
    # 無ければ空行を作る
    _exec("INSERT INTO note_content(room_id,content,updated_at)"
          " VALUES(:r,'',NOW())", {"r": room_id})
    return get_row(room_id)

def save_content(room_id, content):
    _exec("""UPDATE note_content
             SET content=:c, updated_at=NOW()
             WHERE room_id=:r""",
          {"c": content, "r": room_id})
