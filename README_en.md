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
Create a file named `.env` in the project directory and set passwords etc.
(The sample below uses placeholder text, so please change them to your preferred passwords!)

```env
SQL_HOST=db
SQL_USER=user
SQL_PW=password
SQL_DB=fsqr
SECRET_KEY=secret
ADMIN_KEY=admin
MANAGEMENT_PASSWORD=manage
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

## 📜 License
This project is released under the **Apache License 2.0**.
See the `LICENSE` file for details.

Copyright 2026 **Kota Kawagoe**
