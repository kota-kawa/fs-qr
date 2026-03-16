# 📂 FS-QR (File Sharing & QR)

FS-QR is a FastAPI-powered web app that makes file sharing, QR-based downloads, and real-time collaborative notes effortless. It is built to be production-friendly (Docker + MySQL), simple to operate, and easy to showcase in a portfolio.

## 🌟 Highlights
- **Instant sharing via QR codes** — upload a file and scan to download from any device.
- **Group-based collaboration** — create a room with a shared passphrase and share files safely.
- **Real-time notes** — collaborate in a shared note area for ideas and coordination.
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
```

### 3) Run the stack
```bash
docker-compose up --build
```

### 4) Open in your browser
- http://localhost:5000

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
- `DEPLAY_PATH` (or `DEPLOY_PATH`): absolute path to the `fs-qr` checkout on the server

### Server-side prerequisites
- The server must already have Docker and the Docker Compose plugin installed.
- The repository must already be cloned at the path set in `DEPLAY_PATH`.
- A production `.env` must already exist at `DEPLAY_PATH/.env`. The workflow intentionally fails if it is missing.

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
```

### 3) 起動
```bash
docker-compose up --build
```

### 4) ブラウザでアクセス
- http://localhost:5000

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
- `DEPLAY_PATH`（または `DEPLOY_PATH`）: サーバー上の `fs-qr` の絶対パス

### サーバー側の前提
- Docker と Docker Compose plugin がインストール済みであること
- `DEPLAY_PATH` に設定したパスへリポジトリが clone 済みであること
- `DEPLAY_PATH/.env` に本番用の環境変数が用意されていること

## 📜 ライセンス
**Apache License 2.0** にて公開しています。詳細は `LICENSE` を参照してください。

</details>
