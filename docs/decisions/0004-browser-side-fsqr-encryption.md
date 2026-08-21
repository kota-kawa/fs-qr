# ADR-0004: FSQR はブラウザ側でファイルを暗号化する

- 状態: 採用
- 対象: `static/js/fs_qr_upload/encryption.js`、`FSQR/fsqr_app.py`、`FSQR/templates/fs_qr_info/_scripts.html`

## 背景

FSQR はアカウントなしでファイルを共有します。サーバー上の保存物を平文にせず、利用者の
ブラウザから送信される段階で暗号化する必要があります。単一ファイルと複数ファイルで
payload 形式が異なり、保存上限と nginx の request body 上限にも影響します。

## 判断

Web Crypto API の AES-GCM をブラウザで使い、単一ファイルは IV と暗号文、複数ファイルは
各ファイルを `.enc` にして ZIP 化した payload を送信します。ダウンロード後の復号も
ブラウザで行い、サーバーは `.enc` / `.zip` を保存します。サーバー側では暗号化済み
payload の形式、ファイル数、サイズ、ファイル名、保存先を検証します。

## 理由

- 保存時の平文ファイルを作らずに済む。
- 復号鍵を URL fragment / パスワード等の共有フローに分離できる。
- サーバーは認証・認可と保存・配信を担当し、暗号処理をクライアントへ分けられる。

## 影響

- 暗号化・復号、IV、鍵モード、`.enc` suffix を変更すると upload と download の両方が壊れる。
- AES-GCM の envelope で保存 payload が利用者のファイル合計より大きくなるため、アプリと
  nginx の上限を別々に整合させる必要がある。
- JavaScript、テンプレート、サーバー検証、ファイル配信テストを同じ変更で確認する。
- ブラウザの Web Crypto 非対応、鍵の紛失、共有 URL の取り扱いは利用者向け仕様として
  別途説明が必要であり、サーバー側暗号化へ変更する場合はこの ADR を supersede する。
