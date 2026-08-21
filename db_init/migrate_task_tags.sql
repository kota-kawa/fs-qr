-- 手動適用が必要な既存環境向けの参考SQL。
-- 通常のデプロイでは alembic/versions/20260821_0012_task_tags.py が
-- アプリ起動時（migration_runner.run_migrations）に自動で同じ変更を適用する。
--
-- タスクの分類を「カテゴリ」から「タグ」へ統一する。既存の category は同名の
-- タグへ移し替えてから列を落とすため、稼働中のボードでも分類が失われない。
-- Migrates task classification from the single category column to per-room tags.

CREATE TABLE IF NOT EXISTS task_tag (
    tag_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    room_id VARCHAR(255) NOT NULL,
    name VARCHAR(40) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    UNIQUE KEY uq_task_tag_room_name (room_id, name),
    CONSTRAINT fk_task_tag_room_id
        FOREIGN KEY (room_id) REFERENCES task_room(room_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS task_item_tag (
    item_id BIGINT NOT NULL,
    tag_id BIGINT NOT NULL,
    PRIMARY KEY (item_id, tag_id),
    INDEX idx_task_item_tag_tag (tag_id),
    CONSTRAINT fk_task_item_tag_item
        FOREIGN KEY (item_id) REFERENCES task_item(item_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_item_tag_tag
        FOREIGN KEY (tag_id) REFERENCES task_tag(tag_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO task_tag (room_id, name, created_at)
SELECT DISTINCT room_id, TRIM(category), NOW(6)
FROM task_item
WHERE category IS NOT NULL AND TRIM(category) <> '';

INSERT IGNORE INTO task_item_tag (item_id, tag_id)
SELECT i.item_id, t.tag_id
FROM task_item i
JOIN task_tag t ON t.room_id = i.room_id AND t.name = TRIM(i.category)
WHERE i.category IS NOT NULL AND TRIM(i.category) <> '';

ALTER TABLE task_item DROP COLUMN category;
