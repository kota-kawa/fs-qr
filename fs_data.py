import os
#from PIL import Image
# MySQLdbのインポート
import MySQLdb
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



def manage_time():
    secure_id=None

    cursor.execute(
        "SELECT * FROM fsqr WHERE time < DATE_SUB(now(), INTERVAL 1 DAY)")
    result = cursor.fetchall()

    for s in result:
        secure_id = s['secure_id']

    if secure_id != None:
        remove_data(secure_id)
    else:
        return 0


def save_file(uid, id,password, secure_id):
   
    cursor.execute(
        "INSERT INTO fsqr (time,uuid,id,password,secure_id) VALUES (NOW(),%s,%s,%s,%s)", (uid, id,password,secure_id))

    # 保存を実行
    connection.commit()


# ログイン処理
def try_login(id,password):
    # パスワードが検索に引っ掛からなかったときのためにNULLを入れておく
    no = None
    secure_id=None
    cursor.execute(
        " SELECT * FROM fsqr WHERE id = %s AND password = %s", (id,password))
    result = cursor.fetchall()

    # pythonで使えるデータを取得
    for s in result:
        secure_id = s['secure_id']
    
    if secure_id != no:
        return secure_id
    else:
        return False


# データベースから任意のIDのデータを取り出す --- (*7)
def get_data(secure_id):
    cursor.execute(
        " SELECT * FROM fsqr WHERE secure_id = %s ", (secure_id,))
    result = cursor.fetchall()

    # 検索に引っ掛からなかったときのためにNULLを入れておく
    pas = None

    # pythonで使えるデータを取得
    for s in result:
        secure_id = s['secure_id']

    if secure_id == pas:
        return False
    else:
        return result



# 全てのデータを取得する --- (*9)


def get_all():
    cursor.execute(
        " SELECT * FROM fsqr ORDER BY suji DESC")
    result = cursor.fetchall()

    return result


# アップロードされたファイルとメタ情報の削除 --- (*10)


def remove_data(secure_id):
    # ファイルを削除 --- (*11)
    path = STATIC + '/' + secure_id+'.zip'
    second = QR+'/qrcode-'+secure_id+'.jpg'
    os.remove(path)
    os.remove(second)
    # データを削除
    cursor.execute(
        " DELETE FROM fsqr WHERE secure_id = %s ", (secure_id,))
    # 保存を実行
    connection.commit()

def all_remove():
    # データを削除
    cursor.execute(" DELETE FROM fsqr ")
    # 保存を実行
    connection.commit()
