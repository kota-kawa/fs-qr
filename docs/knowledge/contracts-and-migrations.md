# API 契約とマイグレーションの注意点

外部（ブラウザ、共有 URL、Hocuspocus、nginx）や旧コードと取り決めている境界と、DB スキーマを
安全に変える手順をまとめます。設計の全体像は [ARCHITECTURE.md](../../ARCHITECTURE.md)、
判断の理由は `docs/decisions/` にあります。

## 変えてはいけない契約

- 共有 URL とルーム ID: FSQR の復号鍵は URL fragment（`#` 以降）でのみ運び、サーバーへ送りません。
  新規 raw upload は鍵なしの ID / パスワード導線では 409 を返します
  （[ADR-0004](../decisions/0004-browser-side-fsqr-encryption.md)）。share token は
  `share_links.py` でハッシュ保存し、URL 形式はサービス別に固定です。
- legacy URL: 認証情報を含む旧形式の URL は互換のため受け付けます。ログでは `log_config.py` と
  nginx の伏せ字に依存しているため、パス構造を変えるときは両方を更新します。
- セッション namespace と cache key: `room_session.py` / `room_access.py` の namespace、
  `cache_utils.py` の key、旧 module からの再 export 名は Blue-Green 中に旧コードと共存するため
  変えません。
- エラー応答: HTML と JSON の出し分けと翻訳は `api_response.py` に集約します。JSON API は
  `409` を「stale version の削除」「鍵なし raw share」「削除中ルーム」など競合の意味で使い、
  WebSocket は認証・CSRF 不一致を `1008` で閉じます。既存のステータスコードの意味を変える場合は
  フロントの分岐（`static/js/**`）とテストを同じ変更で更新します。
- Hocuspocus との取り決め: `SECRET_KEY`（または `NOTE_YJS_SECRET`）、`REDIS_URL`、
  `PUBLIC_SITE_URL`、MySQL 接続先を web と共有します。`PUBLIC_SITE_URL` とブラウザの `Origin`
  が一致しないと接続を拒否します。トークン形式を変えたら `Note/note_collaboration.py` と
  `hocuspocus/token.js` を同時に変え、`tests/test_note_collaboration.py` と `hocuspocus/*.test.js`
  の両方を通します。
- 翻訳キー: `phrases/**/*.json` は日本語本文そのものがキーです。テンプレート文言を変えると
  全言語のキーが外れて日本語が漏れるため、`locales/README.md` の手順で全言語を同時に更新します。
- 環境変数: 名前と既定値は `.env.example` が正本です。名前を変えるときは `docker-compose.yml` の
  `environment`、`README.md` の例、`scripts/check_env_documentation.py` の結果を揃えます。

## マイグレーションの作り方

1. `alembic/versions/` の最新 head を確認し、`YYYYMMDD_NNNN_<内容>.py` を追加します。
   `down_revision` は必ず現在の head です。並行作業で head が 2 つになったら、片方の
   `down_revision` を付け替えて直列にします。
2. 同じ変更で `db_init/create_tables.sql` を更新します。空 volume の初回起動だけがこの SQL を
   使い、以後は Alembic が唯一の更新経路です。`db_init/migrate_*.sql` は手動適用向けの参考資産
   で、自動では実行されません。
3. スキーマ整合性テストを追加・更新します（`tests/test_task.py` の schema テストが、初期 SQL と
   migration の列構成を静的に比較する例です）。
4. 既存テーブルがある環境で列を足す migration は、テーブル・列の存在確認を入れて冪等にします。
   `CREATE TABLE IF NOT EXISTS` だけの migration は既存環境に列を足しません。
5. 文字コードは `utf8mb4` に統一します（[ADR-0001](../decisions/0001-startup-alembic-migrations.md)、
   `alembic/versions/20260329_0003_unify_table_charsets.py`）。
6. PR には適用される revision 名、既存環境での確認手順、ロールバック手順、停止時間の有無を
   書きます。

## Blue-Green で守ること

- 起動時に各 web コンテナが `alembic upgrade head` を実行し、MySQL `GET_LOCK` で多重実行を
  防ぎます（`migration_runner.py`）。切替の谷間では「新スキーマ × 旧コード」が必ず共存します。
- 列削除、rename、NOT NULL の直追加、既存列の型変更は 2 リリースに分けます（expand: 追加と
  両対応 → contract: 旧コード撤去後に削除）。
- 削除系の状態遷移（Group / FSQR の `deleting → deleted`）は再試行可能に設計されています。
  途中で止まったレコードを scheduler が拾えるかを変更時に確認します。
- migration が失敗した場合、既定では起動を拒否します。`ALLOW_START_WITHOUT_DB=true` は調査用の
  一時緩和であり、本番の恒久設定にしません。

## 過去の事故

- 2026-08-16: `task_item.start_date` を `db_init/create_tables.sql` にだけ追加し、既存環境向けの
  migration を作らなかったため、本番の既存ルームで `GET /api/task/{room_id}/items` が
  `Unknown column` で 500 を返し続けた。`20260816_0011_task_start_date.py` を冪等に追加し、
  初期 SQL と migration を比較する回帰テストを入れて再発を検知できるようにした。
- 2026-03-29: テーブル間で charset が不一致だったため JOIN と照合で問題が出た。`0003` で
  `utf8mb4` に統一した。
- 2026-06-11: share_links の依存関係を修復する migration（`0007`）が必要になった。関連テーブルを
  分けて追加するときは、外部キーと index を同じ revision でそろえる。
