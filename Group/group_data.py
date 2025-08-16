import os
import shutil
import logging
import log_config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# ログ設定
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
    """
    指定されたルームのデータベースレコードと、
    関連するアップロードフォルダおよびその他のファイル（ZIPファイル、QRコード画像など）を削除します。
    """
    # secure_id の検証は room_id にハイフンなどが含まれることがあるため、ここでは省略

    # グループアップロードフォルダのパスを計算（group_app.py と同様の処理）
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    group_uploads = os.path.join(PARENT_DIR, 'static', 'group_uploads')
    room_folder = os.path.join(group_uploads, secure_filename(secure_id))
    
    # ルームに紐づくアップロードフォルダを削除
    if os.path.exists(room_folder):
        try:
            shutil.rmtree(room_folder)
        except Exception as e:
            logger.error("アップロードフォルダの削除に失敗しました: %s. エラー: %s", room_folder, e)

    # データベースから該当ルームのレコードを削除
    query = text("""
        DELETE FROM room WHERE room_id = :secure_id
    """)
    execute_query(query, {"secure_id": secure_id})

# 全てのデータを削除
def all_remove():
    # 全ルーム情報を取得（get_all() は全件取得を行います）
    rooms = get_all()
    
    # グループアップロードフォルダのパス（group_app.py と同じパスを想定）
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)
    group_uploads = os.path.join(PARENT_DIR, 'static', 'group_uploads')

    for room in rooms:
        room_id = room.get("room_id")
        if not room_id:
            continue

        # ルームに対応するアップロードフォルダの削除
        room_folder = os.path.join(group_uploads, secure_filename(room_id))
        if os.path.exists(room_folder):
            try:
                shutil.rmtree(room_folder)
            except Exception as e:
                logger.error("アップロードフォルダの削除に失敗しました: %s. エラー: %s", room_folder, e)
    
    # 最後に、データベースから全ルームのレコードを削除
    query = text("DELETE FROM room")
    execute_query(query)



# 1週間以上経過したルームを削除する関数
def remove_expired_rooms():
    # 1週間以上前のルームを取得するクエリ（MySQLの場合）
    query = text("SELECT room_id FROM room WHERE time < (NOW() - INTERVAL 7 DAY)")
    expired_rooms = execute_query(query, fetch=True)
    for room in expired_rooms:
        room_id = room.get("room_id")
        if room_id:
            remove_data(room_id)
            # ログ出力など必要に応じて追加
