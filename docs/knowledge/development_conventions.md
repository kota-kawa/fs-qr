# 開発規約

コードを変更する作業では、着手前にこの文書を読みます。構成の全体像は
[ARCHITECTURE.md](../../ARCHITECTURE.md)、作業ルールと PR の条件は
[AGENTS.md](../../AGENTS.md) にあり、ここでは重複させずに「どう作るか」だけを書きます。

## プロジェクト構成

FastAPI のエントリーポイントは `app.py` で、`FSQR/`、`Group/`、`Note/`、`Task/`、`Admin/`、
`Articles/` の各 router と、presence / 検索などの横断 router を接続します。共通の DB ヘルパー
は `database.py`、起動時 migration は `migration_runner.py`、設定は `settings.py` にあります。
機能固有のデータ処理は各パッケージ内（例: `Group/group_data.py`）に置きます。HTML テンプレート
はルート `templates/` とモジュールごとの `templates/`、静的アセットは `static/`、翻訳カタログは
`locales/`、MySQL の初期 SQL は `db_init/`、運用中の schema 変更は `alembic/`、Note 共同編集の
Node サーバーは `hocuspocus/` にあります。

ファイル単位の対応関係は `ARCHITECTURE.md` の「リポジトリの地図」「機能モジュール」
「変更箇所からの参照先」を正とし、ここには再掲しません。

## ビルド、テスト、開発用コマンド

- Python コマンドは `python3` で実行します。CI は Python 3.13 と 3.14 の両方でテストし、本番は
  3.14 です。ローカルの `python3` が古い場合は `python3 --version` を確認し、CI と同じ系列で
  仮想環境を作り直してください（3.13 で通らない構文は CI で落ちます）。
- `python3 -m venv .venv && source .venv/bin/activate` で仮想環境を作り、
  `pip install -r requirements.txt` と `pip install -r requirements-dev.txt` を入れます。
  ツールのバージョンを変更する場合は `requirements-dev.txt` と
  `.github/workflows/tests.yml` の `env` を一致させてください。
- `uvicorn app:app --reload --host 0.0.0.0 --port 5000` または `python3 app.py`（同じ uvicorn を
  `--reload` 付きで起動）でローカル起動します。MySQL と Redis が必要です。
- `docker-compose up --build` で本番相当の構成（web-blue / db / redis / hocuspocus / scheduler）を
  起動します。web-blue は host 5000、web-green は profile 指定時に host 5030 を使います。
- `python3 -m pytest tests/test_<対象>.py -q` で変更箇所のテストを実行します。全体は
  `python3 -m pytest -q`。日本語漏れ検査 `tests/test_no_japanese_leakage.py` は件数が多いため
  CI では `-n auto` で並列実行しています。
- `python3 -m ruff check .` と `python3 -m ruff format --check .` で静的解析とフォーマット、
  `python3 -m mypy --config-file pyproject.toml` で `pyproject.toml` に列挙したファイルの型検査を
  行います。
- 翻訳を触ったら `python3 scripts/validate_locales.py --strict-phrases` と
  `python3 scripts/generate_babel_catalogs.py --check` を実行します。カタログの再生成は
  `python3 scripts/generate_babel_catalogs.py`（`--check` なし）で、生成物の `messages.po` も
  コミットします。
- Hocuspocus を触ったら `hocuspocus/` で `npm ci && npm test`、ブラウザ bundle を変えたら
  `npm run build:client` を実行し、生成物 `static/js/note_room_realtime/yjs-collaboration.js` の
  差分をコミットします。CI は生成物が最新であることを `git diff --exit-code` で確認します。
- 文書と設定の同期は `python3 scripts/check_doc_paths.py` と
  `python3 scripts/check_env_documentation.py` で確認します。CI の lint ジョブでも実行されます。
  どちらも `git ls-files` を基準にするため、新しいファイルは `git add`（または `git add -N`）
  してから実行します。
- デプロイ処理を触ったら `bash -n scripts/deploy_bluegreen.sh` と
  `python3 -m pytest tests/test_deploy_bluegreen.py -q` を実行します。

## スキーマ同期

DB スキーマは 3 か所を同じ変更で更新します。

1. `alembic/versions/YYYYMMDD_NNNN_<内容>.py`: 既存環境へ適用する migration。連番 `NNNN` は
   直前の head の次を使い、`down_revision` を必ず head に合わせます。
2. `db_init/create_tables.sql`: 空の Docker volume に使う初期スキーマ。列順を migration と揃えます。
3. スキーマ整合性テスト（`tests/test_task.py` の schema テストと `tests/test_database_behavior.py`
   が例）: 初期スキーマと migration の列構成が一致することを検証します。

適用済みの migration は書き換えません。テーブルが既に存在する環境で列を足す migration は
`_table_exists()` / `_column_exists()` のような存在確認を入れて冪等にします（例:
`alembic/versions/20260816_0011_task_start_date.py`）。Blue-Green 中は旧コードと新スキーマが
共存するため、列削除・rename・NOT NULL 直追加は expand と contract に分けます。詳細と過去の
事故は [contracts-and-migrations.md](contracts-and-migrations.md) にあります。

## 実装規約

- 4 スペースのインデントで PEP 8 に従い、Ruff の設定（`pyproject.toml`、行長 88、`S` ルール）を
  通します。テストでは `assert` と固定パスワードの `S1xx` を per-file-ignore しています。
- ソースコードのコメントは英語または日本語で意図が伝わるように書き、既存ファイルでは周囲の言語に
  合わせます。仕様の根拠はコメントではなく実装とテストで確認し、食い違いを見つけたら同じ変更で
  直します。
- 未使用のヘルパー、過剰な抽象化、コメントアウトした残骸を残しません。依頼された目的に必要な
  範囲だけを変更します。
- 環境変数は `settings.py` の `_env_flag` / `_env_int` / `_env_csv` を通して読み、不正値は既定値へ
  戻します。追加したら `.env.example`、必要なら `docker-compose.yml` の `environment` も更新します。
  新しい色や角丸は `static/css/07-modern-components.css` と `static/css/17-room-access.css` 〜
  `static/css/20-status-page.css` の共通部品が使うトークンに揃えます。
- 例外・エラー応答は `api_response.py` の共通関数で HTML / JSON を出し分け、翻訳は `_()` を通します。
- 秘密情報や認証情報を含む URL をログ・テスト出力・報告に残しません。

## 命名規則

- 関数、ルーターファクトリー、ファイル名（`group_app.py`）は `snake_case`、クラスは `PascalCase`。
- Jinja テンプレートは公開ルートに合わせてハイフン区切り（例: `fs-qr.html`）。大きな画面は
  `*_partials/` に `_content.html` / `_scripts.html` / `_styles.html` を分けます。
- テストモジュールは `tests/test_<対象領域>.py`。
- 共通 CSS は `static/css/NN-<役割>.css` の番号付きファイルで、サービス色は CSS custom property
  で渡します。
- 静的 JS は `static/js/<機能>/` に機能単位、共通基盤は `static/js/shared/` に置きます。
- Alembic は `YYYYMMDD_NNNN_<内容>.py`、ADR は `docs/decisions/` 配下に 4 桁連番 + kebab-case（既存 ADR と同じ形）。
- 概念の呼び名は [用語集](domain_model.md#用語集) に従います。既存の列名などを改名しない理由も
  同じ節にあります。

## 責務分割

- 各パッケージの `__init__.py` はルーターの公開を最小限にとどめ、ルートのロジックは `*_app.py`
  と `*_routes_*.py` に委譲します。データ処理は `*_data.py`、認可は `*_access.py` /
  `*_authorize.py` に置きます。
- 4 サービスで共通の処理（ルーム作成 ID、削除、セッション namespace、期限検索、共有リンク）は
  `room_*.py` と `share_links.py` にあり、既存 import 名・session namespace・cache key は
  wrapper で互換維持します（[shared-service-components.md](shared-service-components.md)）。
- 依存は route（`*_app.py`、`*_routes_*.py`）→ 認可（`room_session.py`、各サービスの
  `*_access.py`・`*_authorize.py`・`Group/group_common.py`）→ data 層（`*_data.py`、
  `room_repository.py`）→ `database.py`・Redis・ファイル保存の向きにし、新しく逆向きの import を
  作りません（data 層が import する `share_links.py` が `web` と `fastapi.Request` に依存して
  いるのは既存の例外です）。data 層は HTTP レスポンスではなく値を返し、応答は route が組み立て
  ます。route に SQL を書きません（既存の例外は DB 管理画面の `Admin/db_admin.py` と
  `Note/note_app.py` の ID 存在確認）。FSQR / Group / Note / Task のパッケージどうしは import
  しません。
- 業務ルール（入力値、有効判定、認可、状態遷移、上限値）の置き場所は
  [domain_model.md](domain_model.md) の「業務ルールの置き場所」に従います。
- 機能から外部サービスと基盤を使うときは既存の境界モジュールを通します。MySQL は
  `database.py`、Redis は `cache_utils.py`・`rate_limit.py`・`presence.py`・
  `Group/group_realtime.py`・`Note/note_realtime.py`、GeoIP は `geoip_update.py`（取得）と
  `i18n_support/geoip.py`（参照）、Hocuspocus のトークンは `Note/note_collaboration.py`、nginx の
  保護配信は `file_serving.py` です（`app.py` のセッションストアと `scheduler.py` のロックは
  プロセスの組み立てとして直接接続します）。新しい外部サービスを足すときは専用モジュールを
  1 つ作り、SDK・HTTP 呼び出し・応答の変換をそこに閉じ込め、設定は `settings.py` から渡します。
- CQRS、Event Sourcing、Entity / Value Object / Repository のクラス階層は採用しません。理由と
  見直す条件は [ADR-0008](../decisions/0008-lightweight-domain-design.md) にあります。
- 1 つのファイルや関数が肥大化しないよう責務ごとに分割し、既存の巨大なファイルに手を入れる
  場合も変更範囲内で読みやすさを戻します。Ruff の `C90`（複雑度 15）を超えたら分割します。
- ログ設定の変更は `log_config.py` に集約し、モジュール間でハンドラーの一貫性を保ちます。

## テスト方針

- 自動テストは `tests/` にあり `pytest` を使います。`tests/conftest.py` が DB、Redis、
  starsessions をモックし、起動時シークレット検証を通すためのテスト用値を `setdefault` します。
  実 DB を必要とするテストは書かず、SQL 生成やスキーマ整合性は静的に検証します。
- 機能を追加・変更したら対応するテストを追加・更新します。CI のカバレッジ閾値は 75% です。
- 主要なフロー（`/fs-qr`、`/group`、`/note`、`/task`、`/admin`）は必要に応じてローカルまたは
  Docker でスモークテストします。終了処理で DB セッションが片付くこと（`db_session.remove()`）
  を回帰させないでください。
- Note と Group のリアルタイム機能を変更する場合は、接続、切断、再接続、複数クライアント間の
  同期、Redis が一時的に使えないときの挙動を確認します（[realtime.md](realtime.md)）。
- Hocuspocus のテストは `hocuspocus/*.test.js`（`npm test`）です。Compose 環境の疎通は
  `npm run smoke:docker` で確認します。
- 実行した自動テストと手動検証、実行できなかった検証とその理由を PR に記載します。

## サブエージェントの指定

- レビュー用サブエージェント: 読み取り専用で動く汎用エージェントを使います。Claude Code では Agent
  ツールの `general-purpose` にモデル `sonnet5`、effort `high` を指定し、Codex ではモデル
  `gpt-6-luna`、reasoning effort `max` を指定します。いずれも「ファイルを編集しない」と明示します。
  他の環境では同等の設定ができる読み取り専用エージェントを使います。
  渡すものは「スコープ」「差分（`git diff main...HEAD` など）」「チェックリスト
  （要件を満たす／スコープ外の変更が無い／不要なコードが無い／テストが通る／禁止事項に触れない）」
  だけで、実装担当の意図や経緯は渡しません。
- 調査用サブエージェント: 読み取り専用（Claude Code では `Explore`）。結論だけを受け取り、
  ファイルの全文を持ち帰らせません。
- 実装を分割する場合: 担当ファイルが重複しないことを着手前に確認し、成果物の受け渡し形式、
  開始条件、最終判定者（ユーザー）を依頼文に書きます。生成物（bundle、`messages.po`、alembic
  head）を触る作業は 1 担当に限定します。
- 指摘は検証してから反映し、反論がある場合はユーザーに上げます。

## 作業の完了条件

変更内容に対応する実装、テスト、ドキュメントがそろい、変更箇所に関連するテスト、Ruff の
静的解析とフォーマット検査、型チェック、（該当する場合）翻訳検証・文書パス検証・環境変数
検証が成功している状態を完了とします。テストや検査を実行できない場合、または既知の失敗が
残る場合は、未確認のまま完了扱いにせず、対象、理由、想定される影響を PR と最終報告に明示して
ください。設定やデータベーススキーマを変更した場合は、`.env.example`、移行手順、ロールバック
手順も更新します。
