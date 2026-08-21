# FS!QR アーキテクチャ

この文書は、FS!QR のフロントエンド、バックエンド、永続化、実行環境を
短時間で把握するための設計概要です。起動手順やデプロイ手順を再掲する場所では
ありません。実際の設定・実装と差異がある場合は、コードと設定ファイルを優先し、
必要ならこの文書を更新してください。

## 読み方

- まず「リポジトリの地図」と「機能モジュール」を読む。
- 変更対象が決まっている場合は、末尾の「変更箇所からの参照先」で該当領域だけを読む。
- 運用コマンドは [README.md](README.md)、Blue-Green の詳細は
  [docs/blue-green-deploy.md](docs/blue-green-deploy.md)、翻訳カタログの規約は
  [locales/README.md](locales/README.md)、EU 対応の前提は
  [docs/eu-readiness.md](docs/eu-readiness.md) を参照する。

## システム概要

```text
Browser
  │ HTTPS / HTTP Upgrade
  ▼
nginx (fs-qr.conf)
  │  static / WebSocket / X-Accel-Redirect / proxy
  ▼
FastAPI app:app (Gunicorn + UvicornWorker, port 5000)
  │
  ├─ app.py middleware, startup/shutdown, router composition
  ├─ feature routers: FSQR / Group / Note / Task / Admin / Articles
  ├─ shared services: session, CSRF, rate limit, i18n, file serving
  ├─ MySQL 8 (async SQLAlchemy / Alembic)
  ├─ Redis (sessions, cache, rate limit, presence, Group / Note pub/sub)
  └─ bind-mounted files: storage / geoip / logs

scheduler.py (single process)
  └─ MySQL cleanup + Redis lock / Note expiration notification
```

本番では web コンテナを blue / green の 2 スロットで交互に起動します。DB、Redis、
scheduler は共有の単一サービスです。アプリの healthcheck が通った後に nginx の
upstream を切り替えます。運用上の前提とロールバックは既存の
[Blue-Green 手順](docs/blue-green-deploy.md)に集約されています。

## リポジトリの地図

```text
app.py                  FastAPI の組み立て、共通ミドルウェア、公開固定ページ
web.py                  Jinja ローダー、テンプレート用ヘルパー、CSRF、URL
settings.py             環境変数から作る実行時設定
database.py             async SQLAlchemy engine / scoped session / query retry
migration_runner.py     起動時 Alembic 実行（MySQL GET_LOCK で排他）
models.py               入力モデル・バリデーション用の Pydantic モデル
FSQR/                   QR ファイル共有のルーター、データ層、テンプレート
Group/                  複数ファイルのルーム、ファイル操作、管理、WebSocket
Note/                   リアルタイムノート、同期・競合解決、export、WebSocket
Task/                   タスクボード、CRUD / 並べ替え / import-export
Admin/                  管理画面と DB 管理画面
Articles/               記事レジストリ、一覧・記事テンプレート
templates/              共通レイアウト、固定ページ、共通部品
static/                 CSS、共通 JS、機能別 JS、画像・動画・PWA 資産
locales/                言語別 ui / js / phrases カタログ
alembic/                運用中のスキーマ変更履歴
db_init/                新規 MySQL volume 用初期 SQL と旧来の SQL 資産
scripts/                翻訳検証、GeoIP 更新、デプロイ等の再利用可能なスクリプト
tests/                  pytest によるルート、データ層、WebSocket、設定、画面検証
Dockerfile              本番イメージ（builder / runtime の multi-stage build）
docker-compose.yml      web-blue / web-green / scheduler / db / redis
fs-qr.conf              nginx の proxy、WS、静的配信、保護ファイル配信
```

`logs/`、`storage/`、`geoip/`、`.deploy/` は実行時に書き込まれる領域です。通常は
ソースコードや設計情報を置きません。`static/group_uploads/` には旧保存先との互換
読み取りが残っているため、新しい Group ファイルの保存先とは区別してください。

## バックエンドの構造

### 起動とリクエストの流れ

1. `app:app` の import 時に `log_config.py` がログと機密パスの伏せ字を設定する。
2. `app.py` が Proxy headers、Redis セッション、静的ファイル mount、共通 middleware
   を登録する。middleware はセキュリティヘッダー、言語コンテキスト、canonical URL、
   リクエスト終了時の DB session cleanup を担当する。
3. startup で GeoIP 更新、Alembic upgrade、FSQR の期限切れ掃除、Group / Note realtime の
   初期化を行う。DB が準備できない場合は、既定では起動を拒否する。
4. `app.include_router(...)` で各機能の router を登録し、HTML、JSON API、WebSocket
   の各 endpoint が同じ middleware を通る。
5. データ層は `database.execute_query()` などを通して MySQL にアクセスする。通常の
   HTTP リクエスト終了時に `db_session.remove()` が実行される。
6. shutdown で GeoIP task と Group / Note realtime の接続を停止する。

### 機能モジュール

| 機能 | 入口 | データ・共通ロジック | UI / realtime | 主な検証先 |
| --- | --- | --- | --- | --- |
| FSQR | `FSQR/fsqr_app.py` | `FSQR/fsqr_data.py`, `file_validation.py`, `file_serving.py` | `FSQR/templates/`, `static/js/fs_qr_upload/`, `static/js/fsqr_landing/` | `tests/test_fsqr.py`, `tests/test_file_serving.py` |
| Group | `Group/group_app.py` | `group_data.py`, `group_storage.py`, `group_common.py` | `Group/templates/`, `static/js/group_landing/`, `static/js/group_room/`, `group_routes_ws.py` | `tests/test_group.py`, `tests/test_group_realtime.py` |
| Note | `Note/note_app.py`, `note_api.py` | `note_data.py`, `note_access.py`, `note_sync.py`, `note_export.py` | `Note/templates/`, `static/js/note_landing/`, `static/js/note_room_realtime/`, `note_ws.py` | `tests/test_note.py`, `tests/test_note_realtime.py`, `tests/test_note_ws.py`, `tests/test_note_export.py` |
| Task | `Task/task_app.py`, `task_api.py` | `task_data.py`, `task_access.py`, `task_authorize.py`, `task_common.py` | `Task/templates/`, `static/js/task_landing/`, `static/js/task_board/` | `tests/test_task.py`, `tests/test_task_io.py` |
| Admin | `Admin/admin_app.py`, `Admin/db_admin.py` | `session_auth.py`, `rate_limit.py` | `Admin/templates/` | `tests/test_admin.py` |
| Articles | `Articles/articles_app.py` | `Articles/articles_registry.py`, `article_locale_shards.py` | `Articles/templates/` | `tests/test_articles.py`, `tests/test_product_landing_pages.py` |

ルートの登録が増えた場合も、feature の `*_app.py` から見てルートの責務が分かる状態を
保ちます。Group、Task の route 分割（`*_routes_*.py`）は、`*_app.py` の登録順を入口と
して追跡します。

### 横断機能

- `room_access.py`: FSQR / Group / Note / Task が、認証済みセッション内のアクセス権を
  同じ形式で保持する。資格情報の検証自体は各機能が行う。
- `share_links.py`: share token の生成、ハッシュ保存、サービス別 URL の組み立てを共通化する。
- `session_auth.py`: 管理系セッションの有効期限と constant-time 比較を扱う。
- `rate_limit.py`: Redis を使う IP 単位の失敗回数制限と、Task 等の操作 backoff。
- `presence.py` / `presence_api.py`: Redis Sorted Set を基本とし、Redis 障害時はプロセス内
  メモリへフォールバックする閲覧者数 API。
- `i18n.py` と `i18n_support/`: 言語解決、サーバー / ブラウザ文言、HTML 変換。
- `security_headers.py` と `log_config.py`: 全レスポンスのセキュリティヘッダーと、URL 内の
  認証情報・共有 token のログ伏せ字。

## フロントエンドの構造

### テンプレート

`web.py` の `Jinja2Templates` は、ルート `templates/` を共通層として、機能別の
`FSQR/templates/`、`Group/templates/`、`Note/templates/`、`Task/templates/`、
`Admin/templates/`、`Articles/templates/` をロードします。共通レイアウト、footer、
modal、presence indicator を変更する場合はルート `templates/` を先に確認します。

機能画面は概ね次の構成です。

```text
feature/templates/*_landing.html       公開ランディング / 作成導線
feature/templates/*_room*.html         ルーム画面
feature/templates/*_partials/          大きな画面の content / scripts / styles 分割
templates/layout.html                  共通 HTML shell / meta / common assets
```

### 静的 JS / CSS

- `static/js/shared/`: namespace、UX、アップロード制限、service worker などの共通基盤。
- `static/js/fs_qr_upload/`: FSQR の暗号化、選択、送信、progress。
- `static/js/group_room/`: Group の一覧、preview、upload、download、remote update。
- `static/js/note_room_realtime/`: WebSocket、同期、self-edit、UI、export。
- `static/js/task_board/`: board state、CRUD、D&D、calendar、view、import-export。
- `static/css/`: 役割別に番号付けされた共通 CSS。機能固有の大きな style は各 template
  の partial に残ることがある。

FSQR はブラウザの Web Crypto AES-GCM で暗号化した payload を送信し、サーバーは
暗号化済みファイルを保存する。複数ファイルは暗号化済みファイルを ZIP にまとめる。
ダウンロード時の復号もブラウザで行うため、送信処理を変更する場合は
`static/js/fs_qr_upload/encryption.js`、`FSQR/templates/fs_qr_info/_scripts.html`、
`FSQR/fsqr_app.py`、`tests/test_fsqr.py` を一緒に確認します。

### 翻訳

`locales/<lang>/ui.json` は Jinja、`js.json` は `window.FSQR_I18N`、
`phrases/**/*.json` は既存テンプレート本文の互換置換に使います。新規 UI は安定キーを
優先し、phrases に日本語本文を新規追加しません。ファイル配置と検証の詳細は
[locales/README.md](locales/README.md)、実行時の言語判定は
`i18n_support/constants.py` と `i18n_support/language.py` を参照します。
現在は `JAPANESE_ONLY_MODE` が有効で、公開ページの表示・hreflang は日本語に固定される
設計です。多言語表示を再開する場合は、サーバー、テンプレート、JS、SEO テストを一括で確認します。

## データとファイル保存

### MySQL

`database.py` は `mysql+aiomysql` の async engine と task-scoped session を作ります。
スキーマの責務は次の通りです。

| 領域 | 主なテーブル | ファイル / データ |
| --- | --- | --- |
| FSQR | `fsqr`、`share_links` | `FSQR_UPLOAD_DIR`（通常は `storage/fsqr_uploads`）の `.enc` / `.zip` |
| Group | `room` | `GROUP_UPLOAD_DIR`（通常は `storage/group_uploads`）の room 別ディレクトリ。旧 `static/group_uploads` は読み取り互換 |
| Note | `note_room`、`note_content` | 本文は DB。接続状態と更新通知は Redis / WebSocket |
| Task | `task_room`、`task_item`、`task_tag`、`task_item_tag` | ルームと board item は DB。分類はカテゴリを持たず、ルーム単位のタグ（`task_tag`）を `task_item_tag` で多対多に紐づける |

`db_init/create_tables.sql` は空の Docker volume を作る初期スキーマ、
`alembic/versions/` は既存環境へ適用する変更履歴です。アプリ起動時は
`migration_runner.py` が MySQL `GET_LOCK` を取得して `alembic upgrade head` を実行します。
スキーマ変更は Blue-Green 中に旧コードと新コードが共存することを前提に、expand/contract
で設計します。

### Redis

Redis は次の共有状態に使われます。

- starsessions の HTTP session store
- `cache_utils.py` のキャッシュ
- `rate_limit.py` の失敗カウンタと block / backoff
- `presence.py` の閲覧者 heartbeat
- Group / Note の接続数管理と room 更新・閉鎖の pub/sub
- scheduler などの単一実行ロック

Redis 障害時の挙動は機能ごとに異なります。presence と Group / Note realtime は限定的な
フォールバックがありますが、認証・レート制限・セッションの前提を無条件にメモリだけで
代替しないため、変更時は [realtime の知識](docs/knowledge/realtime.md) と
[デバッグ手順](docs/knowledge/debugging.md)を確認します。

## 実行環境とデプロイ

### ローカル / コンテナ

- `Dockerfile`: Python 3.14 の builder と runtime を分け、runtime は `kota` 非 root
  ユーザーで Gunicorn を起動する。
- `docker-compose.yml`: `web-blue`（host 5000）と `web-green`（host 5030）は profile
  で選択し、`db`、`redis`、`scheduler` は共有する。
- `gunicorn_conf.py`: worker 数、timeout、keepalive、log path を環境変数から読む。
- `fs-qr.conf`: nginx が WebSocket と通常 HTTP を proxy し、保護されたファイルだけを
  `X-Accel-Redirect` で直接配信する。認証情報を含む legacy URL と share token は access
  log で伏せる。
- `.env.example` と `settings.py`: 秘密情報を含まない設定の形と既定値を確認する。

Blue-Green の具体的な初回設定、sudo、health gate、nginx 切替、rollback は
[docs/blue-green-deploy.md](docs/blue-green-deploy.md)だけを更新先とします。

### バックグラウンド処理

`scheduler.py` は web worker から分離した単一プロセスです。期限切れの FSQR / Group /
Note / Task を掃除し、Note の期限切れを pub/sub で通知します。Blue-Green で scheduler
を二重化しないことが重要です。

## テストと検証の対応表

| 変更 | 最初に見るテスト | 追加で確認するもの |
| --- | --- | --- |
| 共通 middleware / セッション / CSRF | `test_basic_routes.py`, `test_room_access.py`, `test_security_headers.py` | `test_share_links.py`, 関連 feature テスト |
| FSQR upload / download | `test_fsqr.py`, `test_file_serving.py` | 1 GiB 上限、暗号化 payload、X-Accel の両分岐 |
| Group file / WebSocket | `test_group.py`, `test_group_realtime.py` | 接続・切断・再接続、Redis 不在時の影響、path traversal |
| Note sync / WebSocket | `test_note.py`, `test_note_realtime.py`, `test_note_ws.py` | 複数クライアント、競合 merge、期限切れ通知、Redis pub/sub |
| Task board / import-export | `test_task.py`, `test_task_io.py` | CRUD、並べ替え、日付整合、件数上限、タグの追加 / 名前変更 / 削除 |
| 翻訳 / テンプレート | `test_i18n.py`, `test_locale_files.py`, `test_no_japanese_leakage.py` | `python3 scripts/validate_locales.py --strict-phrases` |
| DB / 設定 / デプロイ | `test_data_layers.py`, `test_runtime_config.py`, `test_deploy_bluegreen.py` | `pytest`、Ruff、mypy、Docker / nginx の実環境確認 |

CI の実際のバージョンと順序は `.github/workflows/tests.yml` を正とします。

## 変更箇所からの参照先

| 目的 | 入口 | 一緒に確認する資料 |
| --- | --- | --- |
| 新しい画面・ルート | 対象 feature の `*_app.py` と template | `web.py`、該当 `static/js`、feature テスト |
| DB カラム・テーブル変更 | `alembic/versions/` | `db_init/create_tables.sql`、`migration_runner.py`、expand/contract の ADR |
| アップロード・ダウンロード | `file_validation.py`、`file_serving.py`、feature data 層 | `fs-qr.conf`、`settings.py`、セキュリティ知識 |
| WebSocket / 同期 | `Group/group_routes_ws.py` または `Note/note_ws.py` | realtime 知識、対応テスト、Redis 設定 |
| 翻訳・SEO | `locales/`、`i18n_support/`、template | `locales/README.md`、locale 検証スクリプト |
| 本番切替・障害復旧 | `scripts/deploy_bluegreen.sh` | `docs/blue-green-deploy.md`、デバッグ知識 |

設計概要に一時的な作業経過や環境固有の値を書かないでください。繰り返し使える
失敗パターンは `docs/knowledge/`、採用した設計とトレードオフは `docs/decisions/` に
短い文書として追加します。
