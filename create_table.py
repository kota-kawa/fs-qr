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

# データベース接続の設定
try:
    db = MySQLdb.connect(
        host=host_key,
        user=user_key,
        passwd=pw_key,
        db=db_key,
        charset="utf8"
    )
    cursor = db.cursor()

    # テーブル作成SQL
    create_table_query = """
    CREATE TABLE IF NOT EXISTS room (
        suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
        time DATETIME NOT NULL,               -- レコードの挿入時間
        id VARCHAR(255) NOT NULL,             -- ユーザーID
        password VARCHAR(255) NOT NULL,       -- パスワード
        room_id VARCHAR(255) NOT NULL         -- 部屋ID
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """

    # クエリ実行
    cursor.execute(create_table_query)
    db.commit()
    print("Table 'room' created successfully.")

except MySQLdb.Error as e:
    print(f"Error: {e}")
finally:
    # データベース接続を閉じる
    if db:
        db.close()
