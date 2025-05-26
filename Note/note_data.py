import os, logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from dotenv import load_dotenv

# ── 設定 ───────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

_engine = create_engine(
    f"mysql+pymysql://{os.getenv('SQL_USER')}:{os.getenv('SQL_PW')}"
    f"@{os.getenv('SQL_HOST')}/{os.getenv('SQL_DB')}?charset=utf8mb4",
    pool_recycle=280, pool_size=10, max_overflow=5, pool_pre_ping=True, echo=False
)
_session = scoped_session(sessionmaker(bind=_engine))

def _exec(q, params=None, fetch=False):
    try:
        res = _session.execute(text(q), params or {})
        if fetch:
            return [r._mapping for r in res]
        _session.commit()
    except Exception as e:
        _session.rollback()
        logger.error(e)
        raise

def pich_room_id(id_, password):
    rows = _exec("""SELECT room_id FROM note_room
                    WHERE id=:i AND password=:p""",
                 {"i": id_, "p": password}, fetch=True)
    return rows[0]["room_id"] if rows else False


# ── ルーム作成（既存） ────────────────────────
def create_room(id_, pw, room_id):
    _exec("""INSERT INTO note_room(time,id,password,room_id)
             VALUES(NOW(),:i,:p,:r)""", {"i": id_, "p": pw, "r": room_id})
    _exec("""INSERT IGNORE INTO note_content(room_id,content,updated_at)
             VALUES(:r,'',NOW())""", {"r": room_id})

# ── 最新行取得（★新規） ────────────────────────
def get_row(room_id):
    rows = _exec("""SELECT content, updated_at
                    FROM note_content WHERE room_id=:r""",
                 {"r": room_id}, fetch=True)
    return rows[0] if rows else {"content": "", "updated_at": None}

# ── 本文だけ取得（テンプレ用） ──────────────────
def get_content(room_id):
    return get_row(room_id)["content"]

# ── 保存 ───────────────────────────────────────
def save_content(room_id, content):
    _exec("""INSERT INTO note_content(room_id,content,updated_at)
             VALUES(:r,:c,NOW())
             ON DUPLICATE KEY UPDATE content=:c, updated_at=NOW()""",
          {"r": room_id, "c": content})
