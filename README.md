> 一番下に日本語版もあります

# 📂 FS-QR (File Sharing & QR)

FS-QR is a FastAPI-powered web app that makes file sharing, QR-based downloads, and real-time collaborative notes effortless. It is built to be production-friendly (Docker + MySQL), simple to operate, and easy to showcase in a portfolio.

## 🌟 Highlights
- **Instant sharing via QR codes** — upload a file and scan to download from any device.
- **Group-based collaboration** — create a room with a shared passphrase and share files safely.
- **Real-time notes** — collaborate in a shared note area for ideas and coordination.
- **Redis-backed WebSocket coordination** — connection state is tracked in Redis for multi-instance stability.
- **Production-like local setup** — Docker Compose mirrors the deployment topology.

## 🧭 Why this project stands out
- **Practical UX**: zero-friction sharing using QR codes and short URLs.
- **Clear separation of concerns**: modular FastAPI routing and database helpers.
- **Operational readiness**: containerized services and environment-based configuration.
- **Security-conscious**: central secret management through `.env` (never commit real secrets).

## 🚀 Quick Start (Docker Compose only)
### 1) Prerequisites
- **Docker** and **Docker Compose**
- **Python 3.14** for local development (Python 3.13 remains in the CI
  compatibility matrix during the migration period)
- Local Python commands in this repository should be run with **`python3`**. The
  `python` command is not available in the expected environment.

For local tests and checks, create a virtual environment with Python 3.14 and
install the pinned development toolchain:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2) Create an `.env`
Copy `.env.example` and adjust the secrets:

```bash
cp .env.example .env
```

```env
SQL_HOST=db
SQL_USER=user
SQL_PW=password
SQL_DB=fsqr
MYSQL_ROOT_PASSWORD=root-password
MYSQL_VOLUME_NAME=fsqr_mysql_data_v2
SECRET_KEY=secret
ADMIN_KEY=admin
MANAGEMENT_PASSWORD=manage
DB_ADMIN_PASSWORD=db-admin
REDIS_URL=redis://redis:6379/0
TRUSTED_PROXY_HOSTS=127.0.0.1,::1
RUN_MIGRATIONS_ON_STARTUP=true
ALLOW_START_WITHOUT_DB=false
FRONTEND_DEBUG=false
UPLOAD_MAX_FILES=30
UPLOAD_MAX_TOTAL_SIZE_MB=1024
GROUP_UPLOAD_DIR=/app/storage/group_uploads
GROUP_FILE_LIST_REQUEST_TIMEOUT_MS=10000
NOTE_MAX_CONTENT_LENGTH=10000
NOTE_SELF_EDIT_TIMEOUT_MS=12000
# Optional path to a Japanese TTF/TTC font with TrueType outlines for PDF exports.
NOTE_PDF_FONT_PATH=
```

### 3) Run the stack
The default compose file uses `MYSQL_VOLUME_NAME=fsqr_mysql_data_v2`, which creates a
fresh MySQL volume instead of reusing an older broken `db_data` volume. Run the Docker
preflight first when changing images or reusing an existing volume:

```bash
./scripts/docker_preflight.sh
```

The web app runs as Blue-Green slots (`web-blue` / `web-green`) that are gated behind
Compose profiles, so a bare `docker compose up` starts only `db`, `redis`, and
`scheduler`. For local use, start the `blue` slot explicitly so the app is served on
`127.0.0.1:5000`:

```bash
docker compose --profile blue up --build
```

### 4) Open in your browser
- http://localhost:5000

## 🗃️ Database migrations (Alembic)
Schema changes are managed with Alembic.

```bash
# inside project root
alembic upgrade head
```

The `20260719_0009` migration changes sharing retention to 1, 6, 12, or 24
hours. It shortens existing FSQR, Group, and Note records to 24 hours from
their creation time, so take a database backup before deployment. Rolling back
the schema removes `retention_hours`; it does not restore expired data or the
previous longer expiry timestamps.

Create a new migration:

```bash
alembic revision -m "describe change"
```

When containers start, `web` and `scheduler` run migrations automatically by default.  
To disable this behavior, set:

```env
RUN_MIGRATIONS_ON_STARTUP=false
```

By default, the web app refuses to start if MySQL is not reachable after retries.
This prevents pages from being served while later requests fail with database-backed
500 errors. For emergency debugging only, this can be bypassed with:

```env
ALLOW_START_WITHOUT_DB=true
```

### MySQL volume startup failure
If MySQL repeatedly logs errors such as `Cannot open datafile for read-only: 'mysql.ibd'`
or `Data Dictionary initialization failed`, the persisted Docker volume is corrupted or
incompatible with the running MySQL image. Application retries cannot repair that state.

Run the preflight check to confirm the local Docker volume state:

```bash
./scripts/docker_preflight.sh
```

The current compose default already points to a fresh volume name:

```env
MYSQL_VOLUME_NAME=fsqr_mysql_data_v2
```

If you still see the same `mysql.ibd` error, stop and recreate the containers so the new
volume setting is applied:

```bash
docker compose down
docker compose up --build --force-recreate
```

First inspect and back up the old volume if it contains data you need. If the local data is
disposable, you can also remove all compose volumes:

```bash
docker compose down
docker volume ls | grep fs-qr
docker compose down -v
docker compose up --build
```

For production, restore the MySQL volume from a known-good backup instead of deleting it.

### Runtime upgrade and rollback

The container runtime is Python 3.14 on Debian 13 (trixie), with MySQL 8.4.10 LTS
and Redis 7.4.9. Python 3.14 is the production target; Python 3.13 is retained in
the test matrix as a supported compatibility floor so existing development
environments receive an explicit regression signal while moving to 3.14.

Before deploying this runtime update, validate both Python versions in CI and take
a logical MySQL backup while the old stack is healthy:

```bash
./scripts/docker_preflight.sh
docker compose exec -T db sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --all-databases --single-transaction --routines --events' \
  > mysql-before-runtime-upgrade.sql
docker compose pull db redis
docker compose --profile blue --profile green build web-blue web-green scheduler
docker compose up -d db redis
```

After deployment, confirm `docker compose ps`, `/healthz`, database reads/writes,
and Note/Group WebSocket connection, disconnection, reconnection, and multi-client
synchronization. Redis is used as ephemeral coordination state in this compose
configuration and has no persistent volume; restarting or rolling it back clears
that transient state.

To roll back application/Python/Redis, redeploy the previous Git revision so its
previous image tags and Dockerfile are rebuilt. Do not start an older MySQL binary
against a volume already opened by a newer image. For a MySQL rollback, stop the
stack, select a new `MYSQL_VOLUME_NAME`, deploy the previous revision, and restore
`mysql-before-runtime-upgrade.sql` into that fresh volume. Keep the original volume
untouched until the restored stack has been verified.

Setting `FRONTEND_DEBUG=true` enables frontend debug logs (`console.log/warn/error`).  
Keep it as `false` in production.

Language auto-detection uses the local DB-IP Lite Country MMDB database under `./geoip/dbip-country-lite.mmdb`.  
The app downloads it on startup when missing or stale, then refreshes it in the background according to `GEOIP_UPDATE_INTERVAL_HOURS` (default: 24). You can also run `python3 scripts/update_geoip_db.py` manually. DB-IP Lite is CC BY 4.0 data, so the app automatically renders the required `IP Geolocation by DB-IP` attribution link.

Upload- and note-related limits are also centrally managed via `.env`, and the same values are shared between the frontend `*Config` and backend validation.
Group room files are stored outside `/static` by `GROUP_UPLOAD_DIR` so they are only served through authenticated download and preview routes.

Note WebSocket sync uses an explicit client-side state machine (`bootstrapping/idle/dirty/saving/saving_dirty/offline_dirty`) to handle conflicts.  
If updates from other users arrive while a save is in flight, they are queued instead of being discarded immediately, and applied after the ACK.  
The ACK timeout is not a fixed value either — it adapts to the communication RTT, using `NOTE_SELF_EDIT_TIMEOUT_MS` as a lower bound.

For Note / Group WebSocket connections, a CSRF token tied to the HTTP session is validated during the handshake.
If the token passed from the page rendered in the same session does not match, the handshake is rejected.

The Note page can export the current editor content as UTF-8 TXT or PDF. Docker
installs IPA P Gothic automatically so a TrueType Japanese font is embedded in
the PDF. For a native non-Docker installation, install `fonts-ipafont-gothic` or
set `NOTE_PDF_FONT_PATH` to a Japanese `.ttf` / `.ttc` file with TrueType
outlines. CFF fonts are rejected because they render inconsistently in some PDF
viewers.

## 🧰 Tech Stack
- **FastAPI** (Python 3.14 / Debian 13 trixie)
- **MySQL 8.4.10 LTS**
- **Redis 7.4.9**
- **Docker / Docker Compose**
- **Jinja2 templates & static assets**

## ✅ Suggested demo flow (for interviews)
1. Start the app via Docker Compose.
2. Upload a file → show the generated QR code.
3. Join a group room → demonstrate shared file access.
4. Open the note page → show real-time updates.

## CI/CD & Auto Deploy
- GitHub Actions runs Ruff, pip-audit, mypy, a Trivy image scan, and the complete
  `pytest` suite on Python 3.13 and 3.14 for every push, pull request, and manual dispatch.
- The deploy job runs only on pushes to `main` after the CI job succeeds.
- If deployment secrets are not configured yet, the deploy phase is skipped so regular CI stays green.
- Deployment connects over SSH, updates the server checkout, brings up `db`/`redis`,
  and performs a zero-downtime Blue-Green switch via `scripts/deploy_bluegreen.sh`
  (build the inactive color → wait for `/healthz` → switch the nginx backend → drain
  the old color). If the switch cannot complete, the previous color stays live and the
  Git tree is rolled back to the previous commit.

### Required GitHub Secrets
- `SERVER_HOST`: deployment server hostname or IP
- `SERVER_USER`: SSH login user
- `SERVER_SSH_KEY`: private key for the deploy user
- `SERVER_PORT`: optional SSH port (defaults to `22`)
- `DEPLOY_PATH`: absolute path to the `fs-qr` checkout on the server

### Server-side prerequisites
- The server must already have Docker and the Docker Compose plugin installed.
- The repository must already be cloned at the path set in `DEPLOY_PATH`.
- A production `.env` must already exist at `DEPLOY_PATH/.env`. The workflow intentionally fails if it is missing.

## 📜 License
Released under the **Apache License 2.0**. See `LICENSE` for details.

---

<details>
<summary>🇯🇵 日本語版（クリックして展開）</summary>

# 📂 FS-QR (File Sharing & QR)

FS-QRは、**ファイル共有・QRコード配布・リアルタイムノート**をシンプルに実現するFastAPIアプリです。Docker Composeで本番に近い構成をすぐ再現でき、就職活動のポートフォリオとしても説明しやすい構成になっています。

## 🌟 特長
- **QRコードで即共有**：アップロード後にQRを生成し、スマホから簡単ダウンロード。
- **グループ共有**：合言葉で部屋を作り、メンバー間で安全にファイル共有。
- **共同ノート**：リアルタイムで編集できるノート機能。
- **Redis連携のWebSocket管理**：接続状態をRedisで管理し、複数インスタンスでも安定動作。
- **運用を意識した構成**：Docker Composeで構成を統一。

## 🧭 評価ポイント
- **UXの良さ**：QRコードで手間なく共有できる導線。
- **設計の明快さ**：モジュール分割と責務の整理が分かりやすい。
- **運用性**：環境変数管理＋Dockerで再現性が高い。
- **セキュリティ配慮**：`.env` に秘密情報を集約（実情報はコミットしない）。

## 🚀 起動手順（Docker Composeのみ）
### 1) 前提
- **Docker** と **Docker Compose**
- ローカル開発用の **Python 3.14**（移行期間中は Python 3.13 も CI の互換性マトリクスで検証）
- このリポジトリでローカルの Python コマンドを実行する場合は **`python3`** を使います。
  想定環境では `python` コマンドは利用できません。

ローカルでテスト・検査を実行する場合は、Python 3.14 で仮想環境を作成し、固定済みの
開発ツールを導入します。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2) `.env` を作成
`.env.example` をコピーして、秘密情報を設定します。

```bash
cp .env.example .env
```

```env
SQL_HOST=db
SQL_USER=user
SQL_PW=password
SQL_DB=fsqr
MYSQL_ROOT_PASSWORD=root-password
MYSQL_VOLUME_NAME=fsqr_mysql_data_v2
SECRET_KEY=secret
ADMIN_KEY=admin
MANAGEMENT_PASSWORD=manage
DB_ADMIN_PASSWORD=db-admin
REDIS_URL=redis://redis:6379/0
TRUSTED_PROXY_HOSTS=127.0.0.1,::1
RUN_MIGRATIONS_ON_STARTUP=true
ALLOW_START_WITHOUT_DB=false
FRONTEND_DEBUG=false
UPLOAD_MAX_FILES=30
UPLOAD_MAX_TOTAL_SIZE_MB=1024
GROUP_UPLOAD_DIR=/app/storage/group_uploads
GROUP_FILE_LIST_REQUEST_TIMEOUT_MS=10000
NOTE_MAX_CONTENT_LENGTH=10000
NOTE_SELF_EDIT_TIMEOUT_MS=12000
# PDF出力へ使用するTrueTypeアウトラインの日本語TTF/TTC（通常は未指定で可）
NOTE_PDF_FONT_PATH=
```

### 3) 起動
デフォルトの compose は `MYSQL_VOLUME_NAME=fsqr_mysql_data_v2` を使い、壊れた古い
`db_data` volume を再利用せずに新しい MySQL volume を作ります。イメージ変更後や既存
ボリュームを再利用する場合は、先に Docker の事前診断を実行します。

```bash
./scripts/docker_preflight.sh
```

web アプリは Compose profiles でゲートされた Blue-Green スロット（`web-blue` /
`web-green`）として動くため、素の `docker compose up` では `db`・`redis`・`scheduler`
のみが起動します。ローカルで利用する場合は `blue` スロットを明示的に起動し、
`127.0.0.1:5000` でアプリを配信します。

```bash
docker compose --profile blue up --build
```

### 4) ブラウザでアクセス
- http://localhost:5000

## 🗃️ DBマイグレーション（Alembic）
スキーマ変更は Alembic で管理します。

```bash
alembic upgrade head
```

`20260719_0009` は共有データの保存期間を 1・6・12・24 時間に変更します。既存の
FSQR・Group・Note データも作成時刻から24時間へ短縮されるため、デプロイ前にDBバックアップを
取得してください。スキーマをロールバックしても `retention_hours` 列を削除するだけで、すでに
削除されたデータや以前の長い削除予定日時は復元されません。

新しいマイグレーション作成:

```bash
alembic revision -m "変更内容"
```

コンテナ起動時、`web` と `scheduler` はデフォルトで自動マイグレーションを実行します。  
無効化する場合は以下を設定してください。

```env
RUN_MIGRATIONS_ON_STARTUP=false
```

デフォルトでは、MySQL に接続できない場合 web アプリは起動を停止します。DB が使えないまま
画面だけ表示され、その後 500 エラーになる状態を避けるためです。緊急の調査時だけ、以下で
この挙動を無効化できます。

```env
ALLOW_START_WITHOUT_DB=true
```

### MySQL ボリューム起動失敗
MySQL が `Cannot open datafile for read-only: 'mysql.ibd'` や
`Data Dictionary initialization failed` を繰り返す場合、Docker の永続化ボリュームが破損、
または MySQL イメージと不整合になっています。この状態はアプリ側のリトライでは修復できません。

ローカル Docker ボリュームの状態は、以下で確認できます。

```bash
./scripts/docker_preflight.sh
```

現在の compose は、デフォルトで新しい volume 名を使います。

```env
MYSQL_VOLUME_NAME=fsqr_mysql_data_v2
```

それでも同じ `mysql.ibd` エラーが出る場合は、古いコンテナが残っているため、いったん停止して
新しい volume 設定でコンテナを作り直します。

```bash
docker compose down
docker compose up --build --force-recreate
```

必要なデータがある場合は先に古い volume のバックアップ/復旧方針を確認してください。
ローカル検証用でデータを消してよい場合のみ、すべての compose volume を作り直します。

```bash
docker compose down
docker volume ls | grep fs-qr
docker compose down -v
docker compose up --build
```

本番環境では削除ではなく、正常な MySQL バックアップから復旧してください。

### ランタイム更新とロールバック

コンテナのランタイムは Debian 13（trixie）上の Python 3.14、MySQL 8.4.10 LTS、
Redis 7.4.9 です。本番の基準を Python 3.14 としつつ、既存の開発環境が移行する間も
互換性の退行を明示的に検出できるよう、Python 3.13 を CI のサポート下限として残します。

このランタイム更新をデプロイする前に、CI で両 Python バージョンを検証し、旧スタックが
正常なうちに MySQL の論理バックアップを取得します。

```bash
./scripts/docker_preflight.sh
docker compose exec -T db sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --all-databases --single-transaction --routines --events' \
  > mysql-before-runtime-upgrade.sql
docker compose pull db redis
docker compose --profile blue --profile green build web-blue web-green scheduler
docker compose up -d db redis
```

デプロイ後は `docker compose ps`、`/healthz`、DB の読み書きに加え、Note/Group の
WebSocket 接続・切断・再接続・複数クライアント同期を確認します。この compose 構成の
Redis は永続ボリュームを持たない一時的な協調状態なので、再起動やロールバックで状態が
消えることを前提にしてください。

アプリ/Python/Redis を戻す場合は、直前の Git revision を再デプロイして以前のタグと
Dockerfile から再ビルドします。新しい MySQL イメージで開いたボリュームを古い MySQL
イメージで直接起動しないでください。MySQL を戻す場合はスタックを停止し、新しい
`MYSQL_VOLUME_NAME` を指定して旧 revision を起動し、空のボリュームへ
`mysql-before-runtime-upgrade.sql` を復元します。復元後の動作確認が終わるまで元の
ボリュームは削除しません。

`FRONTEND_DEBUG=true` を設定すると、フロントエンドのデバッグログ（`console.log/warn/error`）を有効化できます。  
本番運用時は `false` のままにしてください。

言語の自動判定には、`./geoip/dbip-country-lite.mmdb` に配置される DB-IP Lite Country MMDB を使用します。  
DBがない場合や古い場合はアプリ起動時に取得し、起動後も `GEOIP_UPDATE_INTERVAL_HOURS`（既定24時間）ごとにバックグラウンド更新します。手動更新は `python3 scripts/update_geoip_db.py` で実行できます。DB-IP LiteはCC BY 4.0データのため、必要な `IP Geolocation by DB-IP` 帰属リンクをアプリが自動表示します。

アップロード/ノート関連の上限値も `.env` で統一管理でき、フロントの `*Config` とバックエンド検証に同じ値が反映されます。

Note の WebSocket 同期はクライアント側で明示的なステートマシン（`bootstrapping/idle/dirty/saving/saving_dirty/offline_dirty`）を使用し、競合時の挙動を固定化しています。  
保存中に他ユーザー更新が来た場合はキューして ACK 後に反映し、ローカル入力の消失を避けます。  
ACK タイムアウトは固定ではなく、`NOTE_SELF_EDIT_TIMEOUT_MS` を下限として通信RTTに応じて動的に調整されます。

Note / Group の WebSocket 接続では、HTTP セッションと紐づく CSRF トークンをハンドシェイク時に検証します。
同一セッションで生成されたトークンが一致しない接続は拒否されます。

ノートページでは、現在のエディタ内容を UTF-8 のTXTまたはPDFとして出力できます。
Docker環境では IPA Pゴシックを自動インストールし、TrueType形式の日本語フォントを
PDFへ埋め込みます。Dockerを使わない環境では `fonts-ipafont-gothic` をインストールするか、
TrueTypeアウトラインの日本語 `.ttf` / `.ttc` を `NOTE_PDF_FONT_PATH` に指定してください。
一部PDFビューアで表示が崩れるCFF形式のフォントは使用できません。

## 🧰 技術スタック
- **FastAPI** (Python 3.14 / Debian 13 trixie)
- **MySQL 8.4.10 LTS**
- **Redis 7.4.9**
- **Docker / Docker Compose**
- **Jinja2テンプレート / 静的アセット**

## ✅ デモの流れ（面接向け）
1. Docker Composeで起動。
2. ファイルをアップロード → QRコード表示。
3. グループページで共有体験を説明。
4. ノートページでリアルタイム更新を確認。

## CI/CD と自動デプロイ
- GitHub Actions で全 push・PR・手動実行時に Ruff、pip-audit、mypy、Trivy による
  イメージ検査、および Python 3.13/3.14 の完全な `pytest` を実行します。
- `main` への push 時のみ、CI 成功後に SSH 経由で本番デプロイを行います。
- デプロイ用 secrets が未設定の間は deploy を skip するため、通常の CI は失敗しません。
- デプロイではサーバー上の checkout を更新し、`db`/`redis` を起動したうえで、`scripts/deploy_bluegreen.sh` による無停止 Blue-Green 切替（非アクティブ色をビルド → `/healthz` を待機 → nginx の backend を切替 → 旧色を drain）を実行します。切替が完了できない場合は旧色を生かしたまま、Git ツリーを直前コミットへロールバックします。

### 必要な GitHub Secrets
- `SERVER_HOST`: デプロイ先サーバーのホスト名またはIP
- `SERVER_USER`: SSHログインユーザー
- `SERVER_SSH_KEY`: デプロイ用秘密鍵
- `SERVER_PORT`: SSHポート（未設定時は `22`）
- `DEPLOY_PATH`: サーバー上の `fs-qr` の絶対パス

### サーバー側の前提
- Docker と Docker Compose plugin がインストール済みであること
- `DEPLOY_PATH` に設定したパスへリポジトリが clone 済みであること
- `DEPLOY_PATH/.env` に本番用の環境変数が用意されていること

## 📜 ライセンス
**Apache License 2.0** にて公開しています。詳細は `LICENSE` を参照してください。

</details>
