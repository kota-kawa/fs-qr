-- Migration to add scalable search and expiration indexes.
-- New rows write password_lookup_hash; legacy rows keep NULL and are handled
-- by the application fallback until they expire.

SET @db := DATABASE();

SET @has_fsqr_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
);

SET @has_fsqr_password_lookup_hash := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND COLUMN_NAME = 'password_lookup_hash'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_fsqr_password_lookup_hash = 0,
    'ALTER TABLE fsqr ADD COLUMN password_lookup_hash VARCHAR(64) NULL',
    'SELECT ''skip add fsqr.password_lookup_hash'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_fsqr_expires_at := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND COLUMN_NAME = 'expires_at'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_fsqr_expires_at = 0,
    'ALTER TABLE fsqr ADD COLUMN expires_at DATETIME NULL',
    'SELECT ''skip add fsqr.expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @has_fsqr_table = 1,
    'UPDATE fsqr SET expires_at = DATE_ADD(time, INTERVAL retention_days DAY) WHERE expires_at IS NULL',
    'SELECT ''skip backfill fsqr.expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @has_fsqr_table = 1,
    'ALTER TABLE fsqr MODIFY expires_at DATETIME NOT NULL',
    'SELECT ''skip modify fsqr.expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_fsqr_id_password_lookup := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND INDEX_NAME = 'idx_fsqr_id_password_lookup'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_idx_fsqr_id_password_lookup = 0,
    'ALTER TABLE fsqr ADD INDEX idx_fsqr_id_password_lookup (id, password_lookup_hash)',
    'SELECT ''skip add fsqr.idx_fsqr_id_password_lookup'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_fsqr_expires_at := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND INDEX_NAME = 'idx_fsqr_expires_at'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_idx_fsqr_expires_at = 0,
    'ALTER TABLE fsqr ADD INDEX idx_fsqr_expires_at (expires_at)',
    'SELECT ''skip add fsqr.idx_fsqr_expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_room_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
);

SET @has_room_expires_at := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
      AND COLUMN_NAME = 'expires_at'
);

SET @sql := IF(
    @has_room_table = 1 AND @has_room_expires_at = 0,
    'ALTER TABLE room ADD COLUMN expires_at DATETIME NULL',
    'SELECT ''skip add room.expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @has_room_table = 1,
    'UPDATE room SET expires_at = DATE_ADD(time, INTERVAL retention_days DAY) WHERE expires_at IS NULL',
    'SELECT ''skip backfill room.expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @has_room_table = 1,
    'ALTER TABLE room MODIFY expires_at DATETIME NOT NULL',
    'SELECT ''skip modify room.expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_room_expires_at := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
      AND INDEX_NAME = 'idx_room_expires_at'
);

SET @sql := IF(
    @has_room_table = 1 AND @has_idx_room_expires_at = 0,
    'ALTER TABLE room ADD INDEX idx_room_expires_at (expires_at)',
    'SELECT ''skip add room.idx_room_expires_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
