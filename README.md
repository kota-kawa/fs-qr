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
Create a `.env` file in the project root:

```env
SQL_HOST=db
SQL_USER=user
SQL_PW=password
SQL_DB=fsqr
SECRET_KEY=secret
ADMIN_KEY=admin
MANAGEMENT_PASSWORD=manage
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
プロジェクト直下に `.env` を作ります。

```env
SQL_HOST=db
SQL_USER=user
SQL_PW=password
SQL_DB=fsqr
SECRET_KEY=secret
ADMIN_KEY=admin
MANAGEMENT_PASSWORD=manage
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

## 📜 ライセンス
**Apache License 2.0** にて公開しています。詳細は `LICENSE` を参照してください。

</details>
