# FS-QR プロジェクト構造

このプロジェクトは機能ごとにモジュール化されて整理されています。

## ディレクトリ構造

```
├── app.py                 # メインアプリケーション（FastAPI）
├── settings.py            # 環境変数の読み込みと共通設定
├── web.py                 # テンプレート/URLヘルパー
├── fs_data.py             # データベース操作（共通）
├── log_config.py          # ログ設定（共通）
│
├── Core/                  # コアファイル共有機能
│   ├── __init__.py
│   ├── core_app.py        # ファイルアップロード・ダウンロード機能
│   └── templates/         # コア機能のテンプレート
│       ├── fs-qr.html
│       ├── fs-qr-upload.html
│       ├── info.html
│       ├── kensaku-form.html
│       ├── after-remove.html
│       └── error.html
│
├── Group/                 # グループファイル共有機能
│   ├── group_app.py       # グループルーム機能
│   ├── group_data.py      # グループデータ操作
│   └── templates/         # グループ機能のテンプレート
│       ├── group.html
│       ├── group_room.html
│       ├── create_group_room.html
│       ├── search_room.html
│       ├── manage_rooms.html
│       └── manage_rooms_login.html
│
├── Note/                  # ノート共有機能
│   ├── note_app.py        # ノートルーム機能
│   ├── note_data.py       # ノートデータ操作
│   ├── note_api.py        # ノートAPI
│   └── templates/         # ノート機能のテンプレート
│       ├── note_menu.html
│       ├── note_room.html
│       ├── note_layout.html
│       ├── create_note_room.html
│       └── search_note_room.html
│
├── Admin/                 # 管理機能
│   ├── __init__.py        # 旧管理機能（下位互換性）
│   ├── admin_app.py       # 新しい管理機能
│   ├── db_admin.py        # データベース管理
│   └── templates/         # 管理機能のテンプレート
│       ├── admin_list.html
│       └── db_admin.html
│
├── Articles/              # 記事・教育コンテンツ
│   ├── __init__.py
│   ├── articles_app.py    # 記事表示機能
│   └── templates/         # 記事のテンプレート
│       ├── articles.html
│       ├── fs-qr-concept.html
│       ├── safe-sharing.html
│       ├── encryption.html
│       ├── education.html
│       ├── business.html
│       └── risk-mitigation.html
│
└── templates/             # 共通テンプレート
    ├── layout.html        # 基本レイアウト
    ├── group_layout.html  # グループ用レイアウト
    ├── index.html         # トップページ
    ├── about.html         # 概要ページ
    ├── contact.html       # 連絡先ページ
    ├── privacy.html       # プライバシーポリシー
    ├── usage.html         # 使い方ページ
    ├── error.html         # エラーページ（共通）
    ├── 404.html          # 404エラーページ
    └── chat_bot.html     # チャットボット
```

## 各モジュールの責任

### Core（コア機能）
- 基本的なファイルアップロード・ダウンロード
- ファイル検索機能
- アップロード完了画面

### Group（グループ機能）
- グループルームの作成・管理
- ルーム内でのファイル共有
- ルーム検索機能

### Note（ノート機能）
- リアルタイムノート共有
- ノートルームの管理
- ノートAPI

### Admin（管理機能）
- ファイル・ルーム管理
- データベース管理
- システム監視

### Articles（記事機能）
- 教育・啓発コンテンツ
- 使い方ガイド
- セキュリティ情報

## 利点

1. **機能ごとの独立性**: 各機能が独立したモジュールになっているため、保守・開発がしやすい
2. **テンプレートの整理**: 機能ごとにテンプレートが分離されているため、関連ファイルが見つけやすい
3. **拡張性**: 新機能を追加する際は新しいモジュールとして追加できる
4. **Note、Adminと同様の構造**: 既存のNote、Adminモジュールと同じパターンで統一性がある
