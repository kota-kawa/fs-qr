# デバッグと検証の入口

この文書は、障害やテスト失敗を再現可能な単位へ切り分けるための入口です。秘密情報を
ログやコマンド履歴へ出さないことを優先し、環境固有の値は記録しません。

## 起動できない

1. `.env.example` と実際の環境変数を比較し、`SQL_HOST`、`SQL_USER`、`SQL_PW`、
   `SQL_DB`、`REDIS_URL`、`SECRET_KEY` が意図した対象を指しているか確認する。
2. Docker なら`db`、`redis`、`hocuspocus`のhealthcheck、アプリの`logs/error.log`、
   各コンテナlogを分けて確認する。
3. `app.py` の startup は GeoIP 更新、DB migration、期限切れ掃除、Group realtime、
   Note期限切れcontrol publisherの順に
   進む。DB migration の失敗は既定では起動拒否であり、`ALLOW_START_WITHOUT_DB=true`
   は調査用の一時的な緩和に過ぎない。
4. 初回の空 volume だけは `db_init/create_tables.sql` が使われる。既存 DB の更新は
   `alembic/versions/` を `migration_runner.py` が実行するため、SQL を直接適用する前に
   Alembic の履歴と `alembic_version` を確認する。

## DB migration の失敗

- 起動ログの missing env / connection refused / migration lock timeout を分ける。
- 複数 web コンテナが同時起動しても、MySQL `GET_LOCK` が migration の同時実行を抑える。
  ロック待ちが続く場合は、別プロセスが DB セッションを保持していないかを確認する。
- Blue-Green の切替中は旧コードと新スキーマが一時共存する。カラム削除、rename、
  新しい NOT NULL の直追加は避け、expand と contract を別リリースに分ける。
- schema の不整合を直すときは、`db_init/create_tables.sql`、最新 Alembic revision、
  該当 data 層、スキーマ検証テストを一つの変更単位として確認する。

## Redis の障害

Redis は全機能で同じ失敗動作ではありません。

- presence は Sorted Set が使えないとプロセス内 store へフォールバックするため、複数
  worker 間の人数は一時的に分割される。
- Note共同編集はRedisをinstance間同期、session認可、store lockに使う。Redis障害時は
  新規接続を認可せず、同期済みに見せるメモリfallbackを行わない。
- Group realtime は Redis pub/sub が使えないと同一プロセス内の接続だけで動く。別 worker /
  別コンテナのファイル更新・ルーム閉鎖通知が届かない可能性がある。Redis 復旧後は購読 task
  が再接続を試みる。
- セッション、レート制限、scheduler の排他は Redis への依存度が高い。フォールバックを
  追加する場合は、認証・安全性・二重実行の影響を先に decision record に残す。

## アップロード・ダウンロードの切り分け

1. ブラウザ側の件数・合計サイズ・暗号化失敗を確認する。
2. nginx の `client_max_body_size`（本番は `1025M`）と、アプリの
   `UPLOAD_MAX_FILES` / `UPLOAD_MAX_TOTAL_SIZE_MB` を分けて確認する。nginx で 413 に
   なった場合はアプリまで届かない。
3. FSQR はブラウザで AES-GCM 暗号化し、保存時に IV 等の envelope 分の余裕を見込む。
   `.enc` / `.zip` の保存先、DB レコード、期限切れ cleanup を照合する。
4. 本番の `X_ACCEL_REDIRECT_ENABLED=true` では、`settings.py` の filesystem root と
   `fs-qr.conf` の `internal alias` が同じホスト領域を指す必要がある。ローカルやテスト
   は `FileResponse` フォールバックを使う。
5. ファイル名は `file_validation.py` と `secure_filename` の境界を確認し、手動で保存先を
   組み立てる修正をしない。

## WebSocket / HTTP の認証失敗

- WebSocket は `csrf_token` と session の `_csrf_token` の一致を確認する。接続時に
  1008 で閉じる場合、資格情報の問題と CSRF の問題を分ける。
- ルーム画面は、まず share token / room credential の検証で session access を付与し、
  その後の HTTP / WS 操作で access と期限を再確認する。
- legacy URL に認証情報が含まれるため、URL をそのままログやテスト出力へ残さない。
  `log_config.py` と nginx の redaction が効いているかを確認する。

Noteの`/yjs`が接続できない場合は、次の順に確認します。

1. nginxの`location = /yjs`がHocuspocusのhost port 1234へupgradeしているか。
2. `PUBLIC_SITE_URL`と`Origin`が完全に同じoriginか。
3. `session` cookieがあり、対応する`starsessions.<id>`に対象roomの`note_room_access`があるか。
4. `note_room`がactiveかつ期限内で、`note_content.yjs_state` migrationが適用済みか。
5. `docker compose logs hocuspocus`でMySQL、Redis、payload上限のどこで拒否されたか。

## テスト失敗の順序

変更対象の小さいテストから始め、次に feature 全体、最後に CI と同じ検証へ進みます。

```bash
python3 -m pytest tests/test_<対象>.py -q
python3 -m pytest -q
python3 -m ruff check .
python3 -m ruff format --check .
python3 -m mypy --config-file pyproject.toml
```

翻訳を変更した場合は `python3 scripts/validate_locales.py --strict-phrases`、
デプロイ処理を変更した場合は `tests/test_deploy_bluegreen.py` を追加で実行します。
環境依存で検証できない場合は、未確認の対象と理由を作業の引き渡しに明記します。
