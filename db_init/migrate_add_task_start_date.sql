-- 手動適用が必要な既存環境向けの参考SQL。
-- 通常のデプロイでは alembic/versions/20260816_0011_task_start_date.py が
-- アプリ起動時（migration_runner.run_migrations）に自動で同じ変更を適用する。
-- 当時の db_init/create_tables.sql の列順（category, start_date, due_date）に合わせている。
-- category は 20260821_0012（db_init/migrate_task_tags.sql）でタグへ移行して削除済み。
ALTER TABLE task_item ADD COLUMN start_date DATE NULL AFTER category;
