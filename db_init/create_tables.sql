CREATE TABLE fsqr (
    suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
    time DATETIME NOT NULL,               -- レコードの挿入時間
    uuid VARCHAR(255) NOT NULL,           -- ユニークな識別子
    id VARCHAR(255) NOT NULL,             -- ユーザーID
    password VARCHAR(255) NOT NULL,       -- パスワード
    secure_id VARCHAR(255) NOT NULL       -- ファイルのセキュアID
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE room (
    suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
    time DATETIME NOT NULL,               -- レコードの挿入時間
    id VARCHAR(255) NOT NULL,             -- ユーザーID
    password VARCHAR(255) NOT NULL,       -- パスワード
    room_id VARCHAR(255) NOT NULL         -- 部屋ID
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
