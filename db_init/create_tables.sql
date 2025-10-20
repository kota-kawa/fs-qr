CREATE TABLE fsqr (
    suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
    time DATETIME NOT NULL,               -- レコードの挿入時間
    uuid VARCHAR(255) NOT NULL,           -- ユニークな識別子
    id VARCHAR(255) NOT NULL,             -- ユーザーID
    password VARCHAR(255) NOT NULL,       -- パスワード
    secure_id VARCHAR(255) NOT NULL,      -- ファイルのセキュアID
    file_type VARCHAR(20) DEFAULT 'multiple', -- ファイルタイプ: single or multiple
    original_filename VARCHAR(255) DEFAULT NULL, -- 単一ファイルの元のファイル名
    retention_days INT NOT NULL DEFAULT 7 -- 自動削除までの日数
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE room (
    suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
    time DATETIME NOT NULL,               -- レコードの挿入時間
    id VARCHAR(255) NOT NULL,             -- ユーザーID
    password VARCHAR(255) NOT NULL,       -- パスワード
    room_id VARCHAR(255) NOT NULL,        -- 部屋ID
    retention_days INT NOT NULL DEFAULT 7 -- 自動削除までの日数
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- =======================
--  ノート共有用テーブル
-- =======================

-- ルームのメタデータ
CREATE TABLE note_room (
    suji INT AUTO_INCREMENT PRIMARY KEY,
    time DATETIME NOT NULL,
    id VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    room_id VARCHAR(255) NOT NULL,
    retention_days INT NOT NULL DEFAULT 7
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 各ルームに 1 行だけ、最新ノート本文を保持
CREATE TABLE note_content (
    room_id VARCHAR(255) PRIMARY KEY,
    content LONGTEXT,
    updated_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

