-- Migration to add retention_days columns for configurable room lifetimes
-- MySQL 5.7 does not support "ADD COLUMN IF NOT EXISTS",
-- so we guard with information_schema checks.

SET @db := DATABASE();

SET @has_room_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
);

SET @has_room_retention_days := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'room'
      AND COLUMN_NAME = 'retention_days'
);

SET @sql := IF(
    @has_room_table = 1 AND @has_room_retention_days = 0,
    'ALTER TABLE room ADD COLUMN retention_days INT NOT NULL DEFAULT 7 COMMENT ''Number of days before automatic deletion''',
    'SELECT ''skip add room.retention_days'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_note_room_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_room'
);

SET @has_note_room_retention_days := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'note_room'
      AND COLUMN_NAME = 'retention_days'
);

SET @sql := IF(
    @has_note_room_table = 1 AND @has_note_room_retention_days = 0,
    'ALTER TABLE note_room ADD COLUMN retention_days INT NOT NULL DEFAULT 7 COMMENT ''Number of days before automatic deletion''',
    'SELECT ''skip add note_room.retention_days'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
