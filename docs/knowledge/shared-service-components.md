# サービス共通コンポーネント

FSQR / Group / Note / Task は、サービスごとの URL、データ層、文言、リアルタイム
処理を維持したまま、同じ画面操作とルーム生命周期の骨格を共有します。この文書は
共通部品を追加・変更するときの入口です。

## バックエンド

- `room_session.py` の `RoomSessionAccess` は、既存のセッション namespace を引数に
  取ります。`group_room_access` などのキーは互換性のため変更しません。
- `room_create.py` は手動 ID の検証、自動 ID の衝突時再試行、409 の判断材料を共有
  します。HTTP レスポンスとサービス固有の保存処理は各 route に残します。
- `room_delete.py` は有効ルーム確認、所有者認可、削除、セッション破棄を
  `RoomDeleteOutcome` に正規化します。ファイル削除や WebSocket 通知は呼び出し側の
  callback で行います。
- `room_repository.py` の `RoomTable` は有効期限 predicate、期限切れ ID、公開 ID と
  パスワードの検索を共有します。テーブル名と列名は固定定数からのみ渡し、値は
  bind parameter を使います。キャッシュ decorator の key は従来の module 名を
  変えないよう、サービス側の互換 wrapper に残します。
- `room_cleanup.py` は scheduler の cleanup 戻り値を一覧へ正規化し、DB 接続 reset
  を `finally` で必ず実行します。Note の期限切れ通知のような後処理は callback に
  渡します。
- `api_response.error_page_or_json` は `Accept` / fetch 判定を一本化し、ブラウザには
  HTML、API には翻訳済み JSON を返します。新しいサービス固有の判定関数を増やさない
  でください。
- `pwa_manifest.py` は 4 サービスの web manifest を 1 ルートから生成します。静的な
  manifest JSON を追加せず、`/manifest/{service}.webmanifest` の表へ値を追加します。

## フロントエンド

- `static/js/shared/share-panel.js` はコピー、共有、QR、feedback toast を担当します。
  QR は ID 固有 selector ではなく `.qr-code-container[data-share-url]` を走査します。
  各 room template はサービス固有の URL 変換と翻訳キーだけを渡します。
- `static/js/shared/instant-widget-core.js` は 4 LP のファイル選択、発行、エラー、
  QR、発行済み状態を共通化します。LP adapter にはサービス固有 endpoint と payload
  差分だけを置き、403 の案内は `FSQR_I18N` または template の data 属性を通します。
- `static/js/shared/file-tray.js` / `progress-spinner.js` は FSQR と Group のアップ
  ロード UI を共有します。FSQR の置換型と Group の追加型は adapter の option で選びます。
- `static/js/shared/custom-select.js` は retention と Task board のキーボード操作を
  共有します。既存の各機能ファイルは薄い adapter として残します。
- `static/css/17-room-access.css`、`18-room-share.css`、`19-transfer-card.css`、
  `20-status-page.css` は、create / search / access、共有 UI、転送カード、ステータス
  画面の重複 CSS をまとめたものです。サービス色は CSS custom property で上書きします。
- `templates/_base.html`、`lp_base.html`、`menu_base.html` と
  `templates/macros/seo.html` は共通 shell、cookie consent、FAQ の JSON-LD / details を
  提供します。SEO 用 FAQ は各呼び出し側で翻訳済みの `faq_items` を作り、macro 内で
  `_()` を呼びません。

## 互換性と変更手順

既存 route の import 名、セッション namespace、翻訳キー、DB schema は維持します。
新しい共通処理へ移す場合も、旧 module からの再 export / wrapper を残し、cache key や
外部から参照される関数名を変えないでください。schema migration はこの共通化では不要
です。

変更時は次を順に確認します。

1. 共通部品自身のテストと `tests/test_room_services_shared.py`。
2. 変更したサービスの route / data / template テスト。
3. 全体の pytest、Ruff、mypy、locale 検証、静的 JavaScript 構文検査。
4. `/fs-qr`、`/group`、`/note`、`/task` と各 LP、manifest のブラウザ確認。

多言語の文言を追加するときは [locales/README.md](../../locales/README.md) の手順に
従い、共通 include / macro に直接日本語の `_()` を書かないでください。
