CREATE TABLE fsqr (
    suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
    time DATETIME NOT NULL,               -- レコードの挿入時間
    uuid VARCHAR(255) NOT NULL,           -- ユニークな識別子
    id VARCHAR(255) NOT NULL,             -- ユーザーID
    password VARCHAR(255) NOT NULL,       -- パスワード
    secure_id VARCHAR(255) NOT NULL,      -- ファイルのセキュアID
    share_token_hash VARCHAR(64) DEFAULT NULL, -- 共有URLトークンのハッシュ
    file_type VARCHAR(20) DEFAULT 'multiple', -- ファイルタイプ: single or multiple
    original_filename VARCHAR(255) DEFAULT NULL, -- 単一ファイルの元のファイル名
    retention_days INT NOT NULL DEFAULT 7, -- 自動削除までの日数
    UNIQUE KEY uq_fsqr_uuid (uuid),
    UNIQUE KEY uq_fsqr_share_token_hash (share_token_hash),
    INDEX idx_fsqr_id_password (id, password),
    INDEX idx_fsqr_secure_id (secure_id),
    INDEX idx_fsqr_time (time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE room (
    suji INT AUTO_INCREMENT PRIMARY KEY,  -- 自動増分の主キー
    time DATETIME NOT NULL,               -- レコードの挿入時間
    id VARCHAR(255) NOT NULL,             -- ユーザーID
    password VARCHAR(255) NOT NULL,       -- パスワード
    room_id VARCHAR(255) NOT NULL,        -- 部屋ID
    retention_days INT NOT NULL DEFAULT 7, -- 自動削除までの日数
    UNIQUE KEY uq_room_room_id (room_id),
    INDEX idx_room_id_password (id, password),
    INDEX idx_room_room_id (room_id),
    INDEX idx_room_time (time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


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
    retention_days INT NOT NULL DEFAULT 7,
    expires_at DATETIME NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    deleted_at DATETIME NULL,
    share_token_hash VARCHAR(64) DEFAULT NULL,
    UNIQUE KEY uq_note_room_room_id (room_id),
    UNIQUE KEY uq_note_room_share_token_hash (share_token_hash),
    INDEX idx_note_room_id_password (id, password),
    INDEX idx_note_room_room_id_password (room_id, password),
    INDEX idx_note_room_time (time),
    INDEX idx_note_room_expires_status (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 各ルームに 1 行だけ、最新ノート本文を保持
CREATE TABLE note_content (
    room_id VARCHAR(255) PRIMARY KEY,
    content LONGTEXT,
    updated_at DATETIME(6),
    version BIGINT NOT NULL DEFAULT 0,
    INDEX idx_note_content_updated_at (updated_at),
    CONSTRAINT fk_note_content_room_id
        FOREIGN KEY (room_id) REFERENCES note_room(room_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

