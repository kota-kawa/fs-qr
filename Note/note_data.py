import os
import logging
import log_config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from dotenv import load_dotenv

# ログ設定
logger = logging.getLogger(__name__)

# .env ファイル読み込み
load_dotenv()
host = os.getenv("SQL_HOST")
user = os.getenv("SQL_USER")
pw   = os.getenv("SQL_PW")
db   = os.getenv("SQL_DB")

# SQLAlchemy エンジンの作成（接続プール設定を含む）
engine = create_engine(
    f"mysql+pymysql://{user}:{pw}@{host}/{db}?charset=utf8mb4",
    pool_recycle=280,    # プール内接続を280秒後に再接続
    pool_size=10,        # 最大10個の接続を保持
    max_overflow=5,      # プール上限後に追加で5個の接続を許可
    pool_pre_ping=True,  # 接続前に疎通確認
    echo=False           # SQL ログ出力（開発時は True、運用時は False）
)

# セッション設定
db_session = scoped_session(sessionmaker(bind=engine))

# 共通クエリ実行関数
def execute_query(query, params=None, fetch=False):
    """
    SQL クエリを実行するユーティリティ。
    :param query: SQL テキストまたは sqlalchemy.text オブジェクト
    :param params: バインドパラメータ用辞書
    :param fetch: 結果を取得する場合は True
    :return: fetch=True の場合は結果リスト、それ以外は影響行数
    """
    try:
        stmt = query if hasattr(query, 'bindparams') else text(query)
        if params:
            result = db_session.execute(stmt, params)
        else:
            result = db_session.execute(stmt)

        if fetch:
            return [row._mapping for row in result]
        else: # INSERT, UPDATE, DELETE の場合
            db_session.commit()
            return result.rowcount # <--- 変更: 影響行数を返す
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        db_session.rollback()
        raise

# note_app.py などから使用するエイリアス関数
_exec = execute_query

# テーブル定義
CREATE_NOTE_ROOM = """
CREATE TABLE IF NOT EXISTS note_room(
  suji INT AUTO_INCREMENT PRIMARY KEY,
  time DATETIME NOT NULL,
  id VARCHAR(255) NOT NULL,
  password VARCHAR(255) NOT NULL,
  room_id VARCHAR(255) NOT NULL,
  retention_days INT NOT NULL DEFAULT 7
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

CREATE_NOTE_CONTENT = """
CREATE TABLE IF NOT EXISTS note_content(
  room_id VARCHAR(255) PRIMARY KEY,
  content LONGTEXT,
  updated_at DATETIME(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# テーブル作成チェック
def _ensure_tables():
    execute_query(CREATE_NOTE_ROOM)
    execute_query(CREATE_NOTE_CONTENT)
    # 既存テーブルをマイクロ秒精度に更新
    try:
        execute_query("ALTER TABLE note_content MODIFY updated_at DATETIME(6)")
    except Exception:
        pass
    logger.info("note tables checked/created")

# アプリ起動時にテーブルをチェック/作成
_ensure_tables()

# ────────────────────────────────────────────
# ノートルーム作成
# ────────────────────────────────────────────
def create_room(id_, password, room_id, retention_days=7):
    execute_query(
        """
        INSERT INTO note_room(time, id, password, room_id, retention_days)
        VALUES(NOW(), :i, :p, :r, :retention)
        """,
        {"i": id_, "p": password, "r": room_id, "retention": retention_days}
    )

# ────────────────────────────────────────────
# ルームメタ情報取得
# ────────────────────────────────────────────
def get_room_meta(room_id, password=None):
    if password is None:
        query = "SELECT id, password, time, retention_days FROM note_room WHERE room_id=:r"
        params = {"r": room_id}
    else:
        query = (
            "SELECT id, password, time, retention_days "
            "FROM note_room WHERE room_id=:r AND password=:p"
        )
        params = {"r": room_id, "p": password}

    rows = execute_query(query, params, fetch=True)
    return rows[0] if rows else None

# ────────────────────────────────────────────
# ID とパスワードで room_id を取得
# ────────────────────────────────────────────
def pick_room_id(id_, password):
    rows = execute_query(
        "SELECT room_id FROM note_room WHERE id=:i AND password=:p",
        {"i": id_, "p": password},
        fetch=True
    )
    return rows[0]["room_id"] if rows else False

# エイリアス（タイポ呼び出し対応）
pich_room_id = pick_room_id

# ────────────────────────────────────────────
# コンテンツ取得 or 初期レコード作成
# ────────────────────────────────────────────
def get_row(room_id):
    rows = execute_query(
        "SELECT * FROM note_content WHERE room_id=:r",
        {"r": room_id},
        fetch=True
    )
    if rows:
        return rows[0]
    # レコードがなければ初期レコードを作成
    execute_query(
        "INSERT INTO note_content(room_id, content, updated_at) VALUES(:r, '', NOW(6))",
        {"r": room_id}
    )
    return get_row(room_id)

# get_row のエイリアス（他プログラム互換）
fetch_note = get_row

# ────────────────────────────────────────────
# コンテンツ保存
# ────────────────────────────────────────────
def save_content(room_id, content, expected_updated_at_str=None):
    if expected_updated_at_str:
        # MySQLのDATETIME(6)型は 'YYYY-MM-DD HH:MM:SS.ffffff' 形式の文字列と比較可能
        query = text("""
            UPDATE note_content
            SET content=:c, updated_at=NOW(6)
            WHERE room_id=:r AND updated_at = :expected_ua
        """)
        params = {"c": content, "r": room_id, "expected_ua": expected_updated_at_str}
        return execute_query(query, params)
    else:
        # expected_updated_at_str がない場合は無条件更新（フォールバックまたは特定用途）
        query = text("UPDATE note_content SET content=:c, updated_at=NOW(6) WHERE room_id=:r")
        params = {"c": content, "r": room_id}
        return execute_query(query, params)

# save_content のエイリアス
store_content = save_content


# ────────────────────────────────────────────
# １週間以上経過したノートルームを削除
# ────────────────────────────────────────────
def remove_expired_rooms():
    try:
        # 7日より古い room_id を取得
        rows = execute_query(
            """
            SELECT room_id
            FROM note_room
            WHERE DATE_ADD(time, INTERVAL retention_days DAY) <= NOW()
            """,
            fetch=True
        )
        for r in rows:
            rid = r["room_id"]
            # コンテンツとルーム情報を順に削除
            execute_query(
                "DELETE FROM note_content WHERE room_id = :r",
                {"r": rid}
            )
            execute_query(
                "DELETE FROM note_room WHERE room_id = :r",
                {"r": rid}
            )
            logger.info(f"Expired note room removed: {rid}")
    except Exception as e:
        logger.error(f"Failed to remove expired note rooms: {e}")
