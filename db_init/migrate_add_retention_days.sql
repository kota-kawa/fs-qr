-- Migration to add retention_days columns for configurable room lifetimes
-- Execute this script after deploying the application change to allow
-- selecting the automatic deletion period per room.

ALTER TABLE room
    ADD COLUMN retention_days INT NOT NULL DEFAULT 7 COMMENT 'Number of days before automatic deletion';

ALTER TABLE note_room
    ADD COLUMN retention_days INT NOT NULL DEFAULT 7 COMMENT 'Number of days before automatic deletion';
