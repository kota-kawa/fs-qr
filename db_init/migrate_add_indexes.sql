-- Migration to add performance indexes for fsqr/room/note_room/note_content tables
-- MySQL 5.7 does not support "ADD INDEX IF NOT EXISTS",
-- so we guard with information_schema checks.

SET @db := DATABASE();

-- fsqr indexes
SET @has_fsqr_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
);

SET @has_idx_fsqr_id_password := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND INDEX_NAME = 'idx_fsqr_id_password'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_idx_fsqr_id_password = 0,
    'ALTER TABLE fsqr ADD INDEX idx_fsqr_id_password (id, password)',
    'SELECT ''skip add fsqr.idx_fsqr_id_password'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_fsqr_secure_id := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND INDEX_NAME = 'idx_fsqr_secure_id'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_idx_fsqr_secure_id = 0,
    'ALTER TABLE fsqr ADD INDEX idx_fsqr_secure_id (secure_id)',
    'SELECT ''skip add fsqr.idx_fsqr_secure_id'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_fsqr_time := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND INDEX_NAME = 'idx_fsqr_time'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_idx_fsqr_time = 0,
    'ALTER TABLE fsqr ADD INDEX idx_fsqr_time (time)',
    'SELECT ''skip add fsqr.idx_fsqr_time'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- room indexes
SET @has_room_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
);

SET @has_idx_room_id_password := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
      AND INDEX_NAME = 'idx_room_id_password'
);

SET @sql := IF(
    @has_room_table = 1 AND @has_idx_room_id_password = 0,
    'ALTER TABLE room ADD INDEX idx_room_id_password (id, password)',
    'SELECT ''skip add room.idx_room_id_password'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_room_room_id := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
      AND INDEX_NAME = 'idx_room_room_id'
);

SET @sql := IF(
    @has_room_table = 1 AND @has_idx_room_room_id = 0,
    'ALTER TABLE room ADD INDEX idx_room_room_id (room_id)',
    'SELECT ''skip add room.idx_room_room_id'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_room_time := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
      AND INDEX_NAME = 'idx_room_time'
);

SET @sql := IF(
    @has_room_table = 1 AND @has_idx_room_time = 0,
    'ALTER TABLE room ADD INDEX idx_room_time (time)',
    'SELECT ''skip add room.idx_room_time'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- note_room indexes
SET @has_note_room_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_room'
);

SET @has_idx_note_room_id_password := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_room'
      AND INDEX_NAME = 'idx_note_room_id_password'
);

SET @sql := IF(
    @has_note_room_table = 1 AND @has_idx_note_room_id_password = 0,
    'ALTER TABLE note_room ADD INDEX idx_note_room_id_password (id, password)',
    'SELECT ''skip add note_room.idx_note_room_id_password'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_note_room_room_id_password := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_room'
      AND INDEX_NAME = 'idx_note_room_room_id_password'
);

SET @sql := IF(
    @has_note_room_table = 1 AND @has_idx_note_room_room_id_password = 0,
    'ALTER TABLE note_room ADD INDEX idx_note_room_room_id_password (room_id, password)',
    'SELECT ''skip add note_room.idx_note_room_room_id_password'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_note_room_time := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_room'
      AND INDEX_NAME = 'idx_note_room_time'
);

SET @sql := IF(
    @has_note_room_table = 1 AND @has_idx_note_room_time = 0,
    'ALTER TABLE note_room ADD INDEX idx_note_room_time (time)',
    'SELECT ''skip add note_room.idx_note_room_time'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- note_content indexes
SET @has_note_content_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_content'
);

SET @has_idx_note_content_updated_at := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_content'
      AND INDEX_NAME = 'idx_note_content_updated_at'
);

SET @sql := IF(
    @has_note_content_table = 1 AND @has_idx_note_content_updated_at = 0,
    'ALTER TABLE note_content ADD INDEX idx_note_content_updated_at (updated_at)',
    'SELECT ''skip add note_content.idx_note_content_updated_at'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
