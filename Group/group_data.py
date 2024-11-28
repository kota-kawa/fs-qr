import time
import os
from PIL import Image
import qrcode

# MySQLdbのインポート
import MySQLdb
import os
import uuid
from dotenv import load_dotenv

#.envファイルの読み込み
load_dotenv()

# 環境変数の値を取得
host_key = os.getenv("SQL_HOST")
user_key = os.getenv("SQL_USER")
pw_key = os.getenv("SQL_PW")
db_key = os.getenv("SQL_DB")

BASE_DIR = os.path.dirname(__file__)
QR = BASE_DIR+'/static/qrcode'
STATIC = BASE_DIR+'/static/upload'

# データベースへの接続とカーソルの生成
connection = MySQLdb.connect(
    host=host_key,
    user=user_key,
    passwd=pw_key,
    db=db_key,
    # テーブル内部で日本語を扱うために追加
    charset='utf8'
)
cursor = connection.cursor(MySQLdb.cursors.DictCursor)



# グループの部屋の作成
def create_room(id,password, room_id):
    cursor.execute(
        "INSERT INTO room (time,id,password,room_id) VALUES (NOW(),%s,%s,%s)", (id,password,room_id))
    # 保存を実行
    connection.commit()


# ログイン処理
def pich_room_id(id,password):
    # パスワードが検索に引っ掛からなかったときのためにNULLを入れておく
    no = None
    room_id=None
    cursor.execute(
        " SELECT * FROM room WHERE id = %s AND password = %s", (id,password))
    result = cursor.fetchall()

    # pythonで使えるデータを取得
    for i in result:
        room_id = i['room_id']
    
    if room_id != no:
        return room_id
    else:
        return False


# データベースから任意のIDのデータを取り出す
def get_data(secure_id):
    cursor.execute(
        " SELECT * FROM room WHERE room_id = %s ", (secure_id,))
    result = cursor.fetchall()
    # pythonで使えるデータを取得
    for i in result:
        room_id = i['room_id']
    # 検索に引っ掛からなかったときのためにNULLを入れておく
    if room_id == None:
        return False
    else:
        return result



# 全てのデータを取得する --- (*9)
def get_all():
    cursor.execute(
        " SELECT * FROM room_id ORDER BY suji DESC")
    result = cursor.fetchall()

    return result


# アップロードされたファイルとメタ情報の削除
def remove_data(secure_id):
    # ファイルを削除 --- (*11)
    path = STATIC + '/' + secure_id+'.zip'
    second = QR+'/qrcode-'+secure_id+'.jpg'
    os.remove(path)
    os.remove(second)
    # データを削除
    cursor.execute(
        " DELETE FROM room_id WHERE room_id = %s ", (secure_id,))
    # 保存を実行
    connection.commit()

def all_remove():
    # データを削除
    cursor.execute(" DELETE FROM room_id ")
    # 保存を実行
    connection.commit()
