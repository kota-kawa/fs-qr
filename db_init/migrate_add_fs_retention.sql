-- Migration to add retention_days column to fsqr table
-- Execute this script after deploying application changes that support
-- configurable retention periods for FS!QR uploads.

ALTER TABLE fsqr
    ADD COLUMN retention_days INT NOT NULL DEFAULT 7 COMMENT 'Number of days before automatic deletion';
