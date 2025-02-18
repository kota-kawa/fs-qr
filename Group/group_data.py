import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from dotenv import load_dotenv
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .envファイルの読み込み
load_dotenv()

# 環境変数の値を取得
host_key = os.getenv("SQL_HOST")
user_key = os.getenv("SQL_USER")
pw_key = os.getenv("SQL_PW")
db_key = os.getenv("SQL_DB")

BASE_DIR = os.path.dirname(__file__)
QR = os.path.join(BASE_DIR, 'static/qrcode')
STATIC = os.path.join(BASE_DIR, 'static/upload')

# SQLAlchemyエンジンの作成
engine = create_engine(
    f"mysql+pymysql://{user_key}:{pw_key}@{host_key}/{db_key}?charset=utf8mb4",
    pool_recycle=280,
    pool_size=10,
    pool_pre_ping=True,
    max_overflow=5,
    echo=False  # 本番環境ではデバッグログを無効化
)

# セッションの設定
db_session = scoped_session(sessionmaker(bind=engine))

# データベースクエリの共通実行関数
def execute_query(query, params=None, fetch=False):
    try:
        result = db_session.execute(query, params or {})
        if fetch:
            return [row._mapping for row in result]
        db_session.commit()
    except Exception as e:
        logger.error("Database query failed: %s", e)
        db_session.rollback()
        raise

# グループの部屋の作成
def create_room(id, password, room_id):
    query = text("""
        INSERT INTO room (time, id, password, room_id) VALUES (NOW(), :id, :password, :room_id)
    """)
    execute_query(query, {"id": id, "password": password, "room_id": room_id})

# ログイン処理
def pich_room_id(id, password):
    query = text("""
        SELECT room_id FROM room WHERE id = :id AND password = :password
    """)
    result = execute_query(query, {"id": id, "password": password}, fetch=True)
    return result[0]["room_id"] if result else False

# データベースから任意のIDのデータを取り出す
def get_data(secure_id):
    query = text("""
        SELECT * FROM room WHERE room_id = :secure_id
    """)
    result = execute_query(query, {"secure_id": secure_id}, fetch=True)
    return result if result else False

# 全てのデータを取得する
def get_all():
    query = text("""
        SELECT * FROM room ORDER BY suji DESC
    """)
    return execute_query(query, fetch=True)

# アップロードされたファイルとメタ情報の削除
def remove_data(secure_id):
    # パス検証
    if not secure_id.isalnum():
        logger.error("Invalid secure_id: %s", secure_id)
        return

    # ファイル削除処理
    paths = [
        os.path.join(STATIC, f"{secure_id}.zip"),
        os.path.join(QR, f"qrcode-{secure_id}.jpg")
    ]
    for file_path in paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Deleted file: %s", file_path)
            else:
                logger.warning("File not found: %s", file_path)
        except Exception as e:
            logger.error("Failed to delete file: %s. Error: %s", file_path, e)

    # データベースから削除
    query = text("""
        DELETE FROM room WHERE room_id = :secure_id
    """)
    execute_query(query, {"secure_id": secure_id})

# 全てのデータを削除
def all_remove():
    query = text("""
        DELETE FROM room
    """)
    execute_query(query)
