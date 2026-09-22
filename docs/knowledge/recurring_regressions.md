# 繰り返した回帰と再発防止

git の履歴（2024-05 〜 2026-09、約 1,400 コミット）から、同じ型で繰り返した問題と、その後に
入れた防止策を短くまとめます。作業前に「今回の変更はどの型に当たるか」を確認するための文書で、
個別の作業ログではありません。

## 共通化・リファクタ後の回帰（2026-09-06 〜 2026-09-07）

共通テンプレートと共通 JS / CSS を導入した PR #386 の直後に、4 サービスで表示崩れと機能欠落が
8 コミット分見つかりました（PR #387）。

- スクリプト読み込み順: `task_board/select.js` がモジュール読み込み時に `window.FSQRCustomSelect`
  を捕まえる実装で、`_scripts.html` が `defer` 版より先に同期実行されるため未定義のまま固定され、
  カスタムセレクトが一切拡張されなかった。
- 初期化順: FSQR の進捗カード見出しが `window.FSQR_I18N` の読み込み前に翻訳を評価し、常に英語
  フォールバックになった。
- 色の取り違え: ルーム全体の `theme-color` にメニューページ専用の装飾色を流用し、PWA とブラウザ
  UI の色が変わった。
- マクロの出力欠落: FAQ の開閉アイコンが依存していた空の `span` を共通マクロが出力しなくなった。
- 同期例外: `copyToClipboard()` が `.catch()` 登録前に同期 throw し、「コピー失敗」が表示されなかった。
- `aria-describedby` が存在しない id を参照した。

再発防止: 共通部品を変えるときは 4 サービス × （入口・ルーム・LP）を
[frontend_visual_verification.md](frontend_visual_verification.md) の手順で実描画し、
`git show <変更前>:<path>` の旧実装と数値比較する。読み込み順は本番と同じ `_scripts.html` で確認する。

## 初期スキーマと migration のずれ（2026-08-16）

`db_init/create_tables.sql` にだけ列を足し、既存環境向け migration を作らなかったため、本番で
500 が続いた。詳細と手順は [contracts-and-migrations.md](contracts-and-migrations.md)。
再発防止: 初期 SQL と migration の列構成を比較する静的テストを追加した。スキーマ変更は 3 か所
（migration、初期 SQL、テスト）を同じ変更で更新する。

## 翻訳カタログの品質と構造（2026-05 〜 2026-06、約 200 コミット）

22 言語のカタログで、重複キー、JSON 構文エラー、日本語本文キーの不一致による日本語漏れ、
未翻訳の暫定文、リンク連結の崩れが繰り返し発生した。機械的な一括置換で JS 変数名まで
書き換えた revert（2026-06-22）もある。

- 再発防止: `scripts/validate_locales.py --strict-phrases` を CI で必須化し、日本語漏れを
  `tests/test_no_japanese_leakage.py` と `tests/test_strict_multilingual_purity.py` で検出する。
- 2026-08-21 に Babel / Jinja gettext へ移行した後、Babel のバージョン差による PO ヘッダー差分で
  `--check` が環境ごとに揺れたため、ヘッダーを正規化した（`scripts/generate_babel_catalogs.py`）。
- 文言の一括置換は対象ファイル種別を限定し、`static/js` を含めない。

## CI とツールチェーン

- Python の互換: 本番 3.14 でも CI は 3.13 と 3.14 の両方で走る。3.14 だけで通る例外構文で落ちた
  （2026-07-12）。ローカルの `python3` が別系列の場合は CI の結果で判断する。
- ピン留めの同期: `requirements-dev.txt` と `.github/workflows/tests.yml` の `RUFF_VERSION` /
  `PIP_AUDIT_VERSION` を別々に上げるとローカルと CI の結果が食い違う。
- カバレッジ閾値: 一度 67% → 現実値へ調整 → 75% に引き上げた（2026-06-23）。テストを削るときは
  閾値を割らないかを見る。
- Trivy: SBOM 由来の誤検出は `.trivyignore.yaml` に理由つきで登録し、Alpine の OpenSSL や
  `mysql2` の脆弱性は base image / 依存の更新で対処した（2026-08-05、2026-08-28、2026-09-06）。
- CI 専用シークレット: Note 共同編集のトークン生成に必要な `SECRET_KEY` は CI ジョブの `env` と
  `tests/conftest.py` の `setdefault` で与える。実運用の値と共有しない（2026-08-21、2026-09-19）。
- テスト時間: 日本語漏れテストは `-n auto` で並列化し、Docker / Trivy は別ジョブに分離した
  （2026-06-21）。

## デプロイと nginx

- 単一 web コンテナの作り直しで約 1 分の 502 が出ていたため Blue-Green 化した（2026-06-25、
  [ADR-0002](../decisions/0002-blue-green-deployment.md)）。
- `fs-qr.conf` の `/_protected/` alias が本番の配置先と異なり、X-Accel-Redirect のダウンロードが
  404 になった（2026-06-25）。`settings.py` の filesystem root と nginx の alias は同じホスト領域を
  指す必要がある。
- デプロイ実行ユーザーの sudo 権限不足は切替直前に分かると復旧が遅れるため、事前検証を
  `scripts/deploy_bluegreen.sh` に入れた（2026-06-25）。
- アップロード上限を 1 GB に拡張した際、nginx の `client_max_body_size` を先に変えなかったため
  413 で止まった（2026-07-20）。上限はアプリ・nginx・クライアント検証を同時に変える。
- 本番デプロイは `main` push の自動実行から手動実行・承認制へ変えた（2026-09-19、
  [ADR-0007](../decisions/0007-manual-production-deployment.md)）。`production` Environment に
  required reviewer を設定しないと承認待ちにならない。

## ブラウザ側の環境依存

- CSP: 第三者スクリプトのホストが ep1、ep2 のように回転するため固定ホスト名では足りず、
  ドメインのワイルドカードで許可した（2026-07-09）。CSP を変えるときは実ブラウザのコンソールで
  違反を確認する。
- View Transitions: CSS だけでオプトインすると、遷移がスキップされた際の promise reject を誰も
  掴めず未処理 rejection になる（2026-07-26）。`pagereveal` / `pageswap` で受け取って no-op の
  `catch` を付ける。
- Cookie 同意バナーを閉じたときの `aria-hidden` 違反（2026-07-26）と、広告・解析タグの読み込み
  失敗からの復帰（2026-07-12）は、外部タグを条件付きで読み込む箇所で再発しやすい。
- PDF 出力: CFF アウトラインの埋め込みフォントは一部ビューアで崩れるため、TrueType アウトラインの
  日本語フォントだけを受け付ける（2026-07-16、`NOTE_PDF_FONT_PATH`）。

## リアルタイム機能

- WebSocket の接続状態をプロセス内メモリだけで持っていたため複数 worker で食い違い、Redis 管理へ
  移した（2026-03-29）。Group の realtime も Redis pub/sub に共有化した（2026-08-21、
  [ADR-0005](../decisions/0005-group-realtime-redis-pubsub.md)）。
- Note は独自同期から Yjs / Hocuspocus へ移行した（2026-08-21、
  [ADR-0006](../decisions/0006-note-collaboration-hocuspocus-yjs.md)）。`PUBLIC_SITE_URL` と
  ブラウザ `Origin` の不一致、`SECRET_KEY` の不一致は接続拒否になる。
- Redis 障害時の挙動は機能ごとに違う。安全側（fail-closed）に倒す判断は
  [realtime.md](realtime.md) と [debugging.md](debugging.md) を先に読む。

## データ整合性とセキュリティ（2026-08-17、2026-09-19）

- Task の部分的な日付更新、インポート入力、同時追加上限、削除結果の検証を強化し、stale version の
  削除は 409 を返すようにした。フロントの連打・復元・不正日付表示も同時に直した。
- サービス全体レビュー（PR #388）で、placeholder のままの秘密値で起動できる、ログや Referer に
  秘密が残る、特権ログイン後にセッション ID が回転しない、Redis 障害時にレート制限が開く、
  Group のアップロードと削除が競合する、といった指摘をまとめて修正した。同種の変更では
  `tests/conftest.py` のテスト用シークレットと `settings.validate_security_settings()` の
  条件を合わせて更新する。
