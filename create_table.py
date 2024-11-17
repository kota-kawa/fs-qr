# coding: utf-8

import MySQLdb
import os
from dotenv import load_dotenv

# .envファイルの読み込み
load_dotenv()

# 環境変数の値を取得
host_key = os.getenv("SQL_HOST")
user_key = os.getenv("SQL_USER")
pw_key = os.getenv("SQL_PW")
db_key = os.getenv("SQL_DB")

# データベース接続
try:
    connection = MySQLdb.connect(
        host=host_key,
        user=user_key,
        passwd=pw_key,
        db=db_key,
        charset='utf8'
    )
    cursor = connection.cursor()

    # roomテーブルの作成
    create_table_query = """
    CREATE TABLE room (
        suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
        time DATETIME NOT NULL,               -- レコードの挿入時間
        id VARCHAR(255) NOT NULL,             -- ユーザーID
        password VARCHAR(255) NOT NULL,       -- パスワード
        room_id VARCHAR(255) NOT NULL         -- 部屋ID
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """

    cursor.execute(create_table_query)
    print("Table 'room' created successfully.")

except MySQLdb.Error as e:
    print("Error creating table: {}".format(e))

finally:
    # 接続を閉じる
    if 'cursor' in locals():
        cursor.close()
    if 'connection' in locals() and connection.open:
        connection.close()
