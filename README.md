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
SECRET_KEY=secret
ADMIN_KEY=admin
MANAGEMENT_PASSWORD=manage
DB_ADMIN_PASSWORD=db-admin
REDIS_URL=redis://redis:6379/0
RUN_MIGRATIONS_ON_STARTUP=true
ALLOW_START_WITHOUT_DB=false
FRONTEND_DEBUG=false
UPLOAD_MAX_FILES=10
UPLOAD_MAX_TOTAL_SIZE_MB=500
GROUP_FILE_LIST_REQUEST_TIMEOUT_MS=10000
NOTE_MAX_CONTENT_LENGTH=10000
NOTE_SELF_EDIT_TIMEOUT_MS=12000
```

### 3) Run the stack
Run the Docker preflight first when changing images or reusing an existing volume:

```bash
./scripts/docker_preflight.sh
```

```bash
docker-compose up --build
```

### 4) Open in your browser
- http://localhost:5000

## 🗃️ Database migrations (Alembic)
Schema changes are managed with Alembic.

```bash
# inside project root
alembic upgrade head
```

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

First inspect and back up the volume if it contains data you need. If the local data is
disposable, recreate the database volume:

```bash
docker compose down
docker volume ls | grep fs-qr
docker compose down -v
docker compose up --build
```

For production, restore the MySQL volume from a known-good backup instead of deleting it.

Setting `FRONTEND_DEBUG=true` enables frontend debug logs (`console.log/warn/error`).  
Keep it as `false` in production.

Upload- and note-related limits are also centrally managed via `.env`, and the same values are shared between the frontend `*Config` and backend validation.

Note WebSocket sync uses an explicit client-side state machine (`bootstrapping/idle/dirty/saving/saving_dirty/offline_dirty`) to handle conflicts.  
If updates from other users arrive while a save is in flight, they are queued instead of being discarded immediately, and applied after the ACK.  
The ACK timeout is not a fixed value either — it adapts to the communication RTT, using `NOTE_SELF_EDIT_TIMEOUT_MS` as a lower bound.

For Note / Group WebSocket connections, a CSRF token tied to the HTTP session is validated during the handshake.
If the token passed from the page rendered in the same session does not match, the handshake is rejected.

## 🧰 Tech Stack
- **FastAPI** (Python)
- **MySQL**
- **Docker / Docker Compose**
- **Jinja2 templates & static assets**

## ✅ Suggested demo flow (for interviews)
1. Start the app via Docker Compose.
2. Upload a file → show the generated QR code.
3. Join a group room → demonstrate shared file access.
4. Open the note page → show real-time updates.

## CI/CD & Auto Deploy
- GitHub Actions runs `pytest` and a Docker image build on every push, pull request, and manual dispatch.
- The deploy job runs only on pushes to `main` after the CI job succeeds.
- If deployment secrets are not configured yet, the deploy phase is skipped so regular CI stays green.
- Deployment connects over SSH, updates the server checkout, rebuilds with `docker compose up -d --build`, and rolls back to the previous Git commit if deployment fails.

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
SECRET_KEY=secret
ADMIN_KEY=admin
MANAGEMENT_PASSWORD=manage
DB_ADMIN_PASSWORD=db-admin
REDIS_URL=redis://redis:6379/0
RUN_MIGRATIONS_ON_STARTUP=true
ALLOW_START_WITHOUT_DB=false
FRONTEND_DEBUG=false
UPLOAD_MAX_FILES=10
UPLOAD_MAX_TOTAL_SIZE_MB=500
GROUP_FILE_LIST_REQUEST_TIMEOUT_MS=10000
NOTE_MAX_CONTENT_LENGTH=10000
NOTE_SELF_EDIT_TIMEOUT_MS=12000
```

### 3) 起動
イメージ変更後や既存ボリュームを再利用する場合は、先に Docker の事前診断を実行します。

```bash
./scripts/docker_preflight.sh
```

```bash
docker-compose up --build
```

### 4) ブラウザでアクセス
- http://localhost:5000

## 🗃️ DBマイグレーション（Alembic）
スキーマ変更は Alembic で管理します。

```bash
alembic upgrade head
```

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

必要なデータがある場合は先にバックアップ/復旧方針を確認してください。ローカル検証用でデータを
消してよい場合のみ、DB ボリュームを作り直します。

```bash
docker compose down
docker volume ls | grep fs-qr
docker compose down -v
docker compose up --build
```

本番環境では削除ではなく、正常な MySQL バックアップから復旧してください。

`FRONTEND_DEBUG=true` を設定すると、フロントエンドのデバッグログ（`console.log/warn/error`）を有効化できます。  
本番運用時は `false` のままにしてください。

アップロード/ノート関連の上限値も `.env` で統一管理でき、フロントの `*Config` とバックエンド検証に同じ値が反映されます。

Note の WebSocket 同期はクライアント側で明示的なステートマシン（`bootstrapping/idle/dirty/saving/saving_dirty/offline_dirty`）を使用し、競合時の挙動を固定化しています。  
保存中に他ユーザー更新が来た場合はキューして ACK 後に反映し、ローカル入力の消失を避けます。  
ACK タイムアウトは固定ではなく、`NOTE_SELF_EDIT_TIMEOUT_MS` を下限として通信RTTに応じて動的に調整されます。

Note / Group の WebSocket 接続では、HTTP セッションと紐づく CSRF トークンをハンドシェイク時に検証します。
同一セッションで生成されたトークンが一致しない接続は拒否されます。

## 🧰 技術スタック
- **FastAPI** (Python)
- **MySQL**
- **Docker / Docker Compose**
- **Jinja2テンプレート / 静的アセット**

## ✅ デモの流れ（面接向け）
1. Docker Composeで起動。
2. ファイルをアップロード → QRコード表示。
3. グループページで共有体験を説明。
4. ノートページでリアルタイム更新を確認。

## CI/CD と自動デプロイ
- GitHub Actions で全 push・PR・手動実行時に `pytest` と Docker イメージ build を実行します。
- `main` への push 時のみ、CI 成功後に SSH 経由で本番デプロイを行います。
- デプロイ用 secrets が未設定の間は deploy を skip するため、通常の CI は失敗しません。
- デプロイではサーバー上の checkout を更新し、`docker compose up -d --build` を実行し、失敗時は直前コミットへロールバックします。

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
