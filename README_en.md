[🇯🇵 日本語 (Japanese)](README.md)

# 📂 FS-QR (File Sharing & QR) 🚀

Hello! Welcome to FS-QR! 👋
This app is a convenient tool that makes **file sharing** and **note sharing** easy for everyone.
You can send files to your smartphone using a QR code, or edit a single note together with others! ✨

---

## ✨ What can you do?

- 📱 **Quick Sharing with QR**
  When you upload a file, a QR code appears. Just scan it with your smartphone to download!

- 🏠 **Group File Sharing**
  Create a room with a "passphrase", and everyone can upload and download files together.

- 📝 **Collaborative Note Editing**
  Real-time note feature! Everyone can write down ideas and leave memos together.

---

## 🚀 How to Use (Getting Started)

Here are the steps to run this app on your computer. It's not difficult! 💪

### 1️⃣ Prerequisites
- **Docker** (If you have this, you're good to go!)

### 2️⃣ Create Configuration File
Copy `.env.example` and update the secrets:

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

### 3️⃣ Start the App
Open your terminal (black screen), type the following command, and press Enter!

```bash
docker-compose up --build
```

### 4️⃣ Open in Browser
Once ready, access the following URL in your browser.

👉 `http://localhost:5000`

That's it! 🎉

---

## 🛠️ Technologies Used (A brief introduction)
- ⚡ **FastAPI** (Lightning-fast web framework for Python)
- 🐳 **Docker** (Convenient container platform)

---

## CI/CD & Auto Deploy
- GitHub Actions runs `pytest` on every push, pull request, and manual dispatch.
- The deploy job runs only after a successful push to `main`.
- Deployment connects over SSH, updates the server checkout, rebuilds with `docker compose up -d --build`, and rolls back to the previous Git commit on failure.

### Required GitHub Secrets
- `SERVER_HOST`: deployment server hostname or IP
- `SERVER_USER`: SSH login user
- `SERVER_SSH_KEY`: private key for the deploy user
- `SERVER_PORT`: optional SSH port (defaults to `22`)
- `DEPLOY_PATH`: absolute path to the `fs-qr` checkout on the server

### Server prerequisites
- Docker and the Docker Compose plugin must already be installed.
- The repository must already be cloned at `DEPLOY_PATH`.
- A production `.env` must already exist at `DEPLOY_PATH/.env`. The workflow fails intentionally if it is missing.

---

## 📜 License
This project is released under the **Apache License 2.0**.
See the `LICENSE` file for details.

Copyright 2026 **Kota Kawagoe**
