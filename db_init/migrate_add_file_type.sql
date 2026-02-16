-- Migration to add file_type and original_filename columns to fsqr table
-- MySQL 5.7 does not support "ADD COLUMN IF NOT EXISTS",
-- so we guard with information_schema checks.

SET @db := DATABASE();

SET @has_fsqr_table := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
);

SET @has_file_type := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND COLUMN_NAME = 'file_type'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_file_type = 0,
    'ALTER TABLE fsqr ADD COLUMN file_type VARCHAR(20) DEFAULT ''multiple'' COMMENT ''File type: single or multiple''',
    'SELECT ''skip add fsqr.file_type'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_original_filename := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'fsqr'
      AND COLUMN_NAME = 'original_filename'
);

SET @sql := IF(
    @has_fsqr_table = 1 AND @has_original_filename = 0,
    'ALTER TABLE fsqr ADD COLUMN original_filename VARCHAR(255) DEFAULT NULL COMMENT ''Original filename for single files''',
    'SELECT ''skip add fsqr.original_filename'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
