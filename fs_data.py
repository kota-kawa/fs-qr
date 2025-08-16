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
STATIC = os.path.join(BASE_DIR, 'static', 'upload')

# SQLAlchemyエンジンの作成（接続プール設定を含む）
engine = create_engine(
    f"mysql+pymysql://{user_key}:{pw_key}@{host_key}/{db_key}?charset=utf8mb4",
    pool_recycle=280,  # プール内の接続を280秒後に再接続
    pool_size=10,      # 最大10個の接続を保持
    pool_pre_ping=True,
    max_overflow=5,    # プールが満杯のとき、さらに5個の接続を作成可能
    echo=False         # デバッグのためにSQLをログ出力（本番環境ではFalse推奨）
)

# セッションの設定
db_session = scoped_session(sessionmaker(bind=engine))

# データベースクエリの共通実行関数
def execute_query(query, params=None, fetch=False):
    try:
        if params:
            result = db_session.execute(query, params)
        else:
            result = db_session.execute(query)

        if fetch:
            return [row._mapping for row in result]

        db_session.commit()
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        db_session.rollback()
        raise

# ファイルを保存
def save_file(uid, id, password, secure_id):
    try:
        query = text("""
            INSERT INTO fsqr (time, uuid, id, password, secure_id) 
            VALUES (NOW(), :uid, :id, :password, :secure_id)
        """)
        execute_query(query, {"uid": uid, "id": id, "password": password, "secure_id": secure_id})
        logger.info("File saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise

# ログイン処理
def try_login(id, password):
    try:
        query = text("""
            SELECT secure_id FROM fsqr WHERE id = :id AND password = :password
        """)
        result = execute_query(query, {"id": id, "password": password}, fetch=True)
        if result:
            logger.info("Login successful.")
            return result[0]["secure_id"]
        else:
            logger.warning("Login failed: Invalid credentials.")
            return False
    except Exception as e:
        logger.error(f"Login attempt failed: {e}")
        raise

# データベースから任意のIDのデータを取り出す
def get_data(secure_id):
    try:
        query = text("""
            SELECT * FROM fsqr WHERE secure_id = :secure_id
        """)
        result = execute_query(query, {"secure_id": secure_id}, fetch=True)
        return result if result else False
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        raise

# 全てのデータを取得する
def get_all():
    try:
        query = text("""
            SELECT * FROM fsqr ORDER BY suji DESC
        """)
        return execute_query(query, fetch=True)
    except Exception as e:
        logger.error(f"Failed to fetch all data: {e}")
        raise

# アップロードされたファイルとメタ情報の削除
def remove_data(secure_id):
    try:
        paths = [
            os.path.join(STATIC, f"{secure_id}.zip")
        ]

        for file_path in paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            else:
                logger.warning(f"File not found: {file_path}")

        query = text("""
            DELETE FROM fsqr WHERE secure_id = :secure_id
        """)
        execute_query(query, {"secure_id": secure_id})
    except Exception as e:
        logger.error(f"Failed to remove data: {e}")
        raise

# 全てのデータを削除
def all_remove():
    try:
        query = text("""
            DELETE FROM fsqr
        """)
        execute_query(query)
    except Exception as e:
        logger.error(f"Failed to remove all data: {e}")
        raise

# 1週間以上経過したファイルレコードと関連ファイルを削除する関数
def remove_expired_files():
    try:
        # MySQLのINTERVAL句を使って1週間前より古いレコードを抽出
        query = text("SELECT secure_id FROM fsqr WHERE time < (NOW() - INTERVAL 7 DAY)")
        expired_records = execute_query(query, fetch=True)
        for record in expired_records:
            secure_id = record.get("secure_id")
            if secure_id:
                remove_data(secure_id)
                logger.info(f"Expired record removed: {secure_id}")
    except Exception as e:
        logger.error(f"Failed to remove expired files: {e}")

