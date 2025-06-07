# FS-QR

Flask で作られたファイル共有・ノート共有アプリケーションです。QR コードでファイルを渡したり、グループでファイルを共有したり、リアルタイムでノートを編集することができます。

## 主な機能
- **QR 共有**: `/fs-qr` でファイルをアップロードするとダウンロード用 QR コードが生成されます。
- **グループ共有**: `/group` でルームを作成し、複数ファイルをやり取りできます。
- **ノート共有**: `/note` でノートルームを作成し、共同編集ができます。
- **DB 管理画面**: `/db_admin` から各テーブルの件数や直近のレコードを確認できます。

## セットアップ
1. リポジトリをクローン後、`.env` ファイルを作成し以下の環境変数を設定します。
   ```env
   SQL_HOST=your_db_host
   SQL_USER=your_db_user
   SQL_PW=your_db_password
   SQL_DB=fsqr
   SECRET_KEY=flask_secret
   ADMIN_KEY=admin_password
   MANAGEMENT_PASSWIRD=management_password
   ```
2. Docker と docker-compose が利用できる環境で次を実行します。
   ```bash
   docker-compose up --build
   ```
3. ブラウザで `http://localhost:5000` にアクセスするとメニュー画面が表示されます。

## ディレクトリ構成
- `app.py` – メインアプリケーション
- `Group/` – グループ共有機能
- `Note/` – ノート共有機能
- `db_init/` – MySQL 初期化用 SQL
- `static/`, `templates/` – 静的ファイルとテンプレート

## ライセンス
MIT
