-- Migration to add file_type and original_filename columns to fsqr table
-- Execute this to support single file encryption feature

ALTER TABLE fsqr 
ADD COLUMN file_type VARCHAR(20) DEFAULT 'multiple' COMMENT 'File type: single or multiple',
ADD COLUMN original_filename VARCHAR(255) DEFAULT NULL COMMENT 'Original filename for single files';