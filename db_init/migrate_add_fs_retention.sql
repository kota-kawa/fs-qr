-- Migration to add retention_days column to fsqr table
-- MySQL 5.7 does not support "ADD COLUMN IF NOT EXISTS",
-- so we guard with information_schema checks.

SET @db := DATABASE();

SET @has_fsqr_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
);

SET @has_retention_days := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND COLUMN_NAME = 'retention_days'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_retention_days = 0,
    'ALTER TABLE fsqr ADD COLUMN retention_days INT NOT NULL DEFAULT 7 COMMENT ''Number of days before automatic deletion''',
    'SELECT ''skip add fsqr.retention_days'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
