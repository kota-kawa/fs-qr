# ドメインモデルと要件の整理

新機能や仕様変更の要件を整理するとき、用語・状態・業務ルールに触れる変更に着手するときに
読みます。モジュール構成とリクエスト経路は [ARCHITECTURE.md](../../ARCHITECTURE.md)、外部と
取り決めた契約は [contracts-and-migrations.md](contracts-and-migrations.md)、共通部品の拡張規則は
[shared-service-components.md](shared-service-components.md) にあり、ここでは再掲しません。
採用しない設計パターンとその理由は [ADR-0008](../decisions/0008-lightweight-domain-design.md)
にあります。

## 要件の整理手順

機能一覧から書き始めず、次の順に整理します。前の段階が決まらないうちは次へ進みません。

1. 価値: 誰が何のために使うかを 1〜2 文で書く。下の「サービスの価値と利用場面」のどれを強める
   変更なのかを明示する。
2. 利用場面と外部との入出力: どんな場面で使うか、送り手・受け手の端末（PC、スマホでの QR
   読み取り）、ブラウザ、nginx、MySQL、Redis、Hocuspocus など入出力の相手と、やり取りするもの
   （ファイル、URL、鍵、通知）を並べる。
3. システム境界: どのサービス（FSQR / Group / Note / Task / Admin / Articles）の責務か、共通層
   （`room_*.py` など）に置くべきかを決める。境界をまたぐ場合は URL、session namespace、
   API の status code などの契約への影響を確認する。
4. 機能・データ・状態: 利用者の操作を下の「利用の流れ」に沿って時系列に並べ、変更がどの段階の
   どの操作に入るかを決める。そのうえで、最初に必要な機能と後回しにできる機能を分けて優先順位を
   付け、必要な列、状態、上限値、翻訳キーを洗い出す。

依頼文の中身は次の 3 つに分けて扱います。

| 区分 | 意味 | 扱い |
| --- | --- | --- |
| 要望 | 「あったらいい」という希望。実現手段の指定を含むことが多い | そのまま実装しない。背景にある要求を確認する |
| 要求 | 要望の背景にある、利用者が達成したいこと | 価値と利用場面に照らして、採否をユーザーと相談する |
| 要件 | 実装すると合意した振る舞いと制約。受け入れ条件として書ける | これだけを実装とテストの対象にする |

採用しなかった要望と要求は捨てずに、PR 本文のスコープ外と最終報告に残します。

## サービスの価値と利用場面

4 サービスに共通する価値は、アカウント登録なしにブラウザだけで使えることと、保存期間が
過ぎると共有した内容（ファイル、ノート本文、タスク）が自動削除されることです。長期保存、
利用者の識別、操作履歴の蓄積を前提にする機能は、この価値と衝突しないかを最初に確認します。

| サービス | 誰が何のために | 主な利用場面 |
| --- | --- | --- |
| FSQR | 送り手が、ファイルをブラウザで暗号化して一時的に相手へ渡す | 別の端末や相手へ QR コード・共有URL で渡す |
| Group | 参加者が、1 つのルームにファイルを集めて配る | 社内資料・授業資料・イベント配布物、取引先との受け渡し |
| Note | 参加者が、同じノートを同時に編集する | 会議メモ、議事録、一時的な共有メモ |
| Task | 参加者が、共有後の作業をカンバンで追う | イベント準備、ミーティングの TODO、チームの分担管理 |

## 利用の流れ

4 サービスは同じ流れを共有し、共通部品もこの段階ごとに分かれています。新機能はどの段階の
どの操作に入るかを決めてから設計し、他のサービスの同じ段階にも変更が要るかを確認します。

| 段階 | 利用者の操作 | 主な実装 |
| --- | --- | --- |
| 1. 作成 | ルームID（自動 / 手動）と保存期間を選んで作成する。FSQR はルームを作らず、アップロード時に ID とパスワードを発行する | `room_create.py`（FSQR は通らない）、`models.py`、`static/js/shared/instant-widget-core.js` |
| 2. 共有 | 発行されたルームID・パスワード・共有URL・QR コードを相手へ渡す | `share_links.py`、`static/js/shared/share-panel.js` |
| 3. 入室 | 共有URL / QR を開くか、ルームID とパスワードで検索して入る。FSQR の現行のアップロードは復号鍵が共有URL にしか無いため、検索からは受け取れない（409） | `room_repository.py`、`room_session.py`、`room_access.py`、`top_search.py` |
| 4. 利用 | ダウンロード、アップロード、同時編集、タスク操作などサービス固有の操作をする | 各サービスの `*_app.py`、`*_routes_*.py`、`*_data.py` |
| 5. 終了 | 作成者が削除するか、保存期間の経過で自動削除される。FSQR / Group は管理画面からも削除できる | `room_delete.py`、`room_cleanup.py`、`scheduler.py`、`Admin/admin_app.py`、`Group/group_routes_manage.py` |

## 用語集

画面・API・DB・コード・文書で、同じ概念は同じ名前で呼びます。既存コードには歴史的な別名が
残っていますが、列名・session namespace・cache key・URL は旧コードと共存する契約なので、
呼び名を揃える目的だけで改名しません。新しいコード・文書・翻訳では「画面での名前」と
「コードでの名前」の列にある名前を使い、別名を増やしません。新しい概念を追加するときは、
同じ変更でこの表に追記します。

| 画面での名前 | コードでの名前 | DB | 既存の別名と注意 |
| --- | --- | --- | --- |
| ルーム | room | `room`（Group）、`note_room`、`task_room` | Group のテーブル名は歴史的に `room`。FSQR はルームを作らず、1 回のアップロードが単位になる |
| ルームID | `room_id`（ID とパスワードでの検索時は `id`） | Group / Note / Task は `id` と `room_id` に同じ値、FSQR は `fsqr.id` | 半角英数字 6 文字（`models.py` の `ROOM_ID_RE`）。一意なのはサービスの中だけで、FSQR の `fsqr.id` には一意制約が無い。FSQR の画面では「共有ID」「ID」と表記する。Group のデータ層の引数 `secure_id`、FSQR のフォーム項目 `name`、`room_repository.py` の `public_id`、`db_init/create_tables.sql` のコメント「ユーザーID」もこれを指す |
| （画面での名前なし） | `secure_id` | `fsqr.secure_id` | FSQR のアップロード 1 件を指すキー。`{ルームID}-{uuid の先頭 10 文字}-{送信ファイル名}` の形で（組み立ては `FSQR/fsqr_app.py`）、保存ファイル名、共有リンクの `resource_id`、`/download/{secure_id}` などの URL に使う。複数ファイルの info 画面ではファイル名として表示される |
| パスワード | `password` | `password`（ハッシュ）、FSQR は `password_lookup_hash` も持つ | 6 桁の数字。Group / Note / Task はサーバーが発行し、FSQR はブラウザが生成して送る（無ければサーバーが発行）。FSQR ではダウンロードの認証にだけ使い、暗号鍵とは別物（[ADR-0004](../decisions/0004-browser-side-fsqr-encryption.md)）。DB にはハッシュだけを保存し、ログに出さない |
| 共有URL | `share_url`、`share_token` | `share_links.token_hash` | 画面では「共有URL」と「共有リンク」が併用されているが、新しい文言は「共有URL」に揃える。token は DB にハッシュだけを保存する。`fsqr` / `note_room` / `task_room` の `share_token_hash` は旧形式の列で、現行コードは書き込まない（FSQR だけが旧 token の解決に読む） |
| 保存期間 | `retention_hours` | `retention_hours`、`expires_at` | 作成フォームのラベルは「自動削除までの期間」。FSQR / Group は 1・6・12・24 時間、Note / Task は 1 日・1 週間・1 か月で、不正値は 24 時間に戻す（`models.py`）。`retention_days` は旧互換の列で常に 1 |
| 自動削除 | expire / cleanup | `expires_at <= NOW()` の行 | 保存期間の経過による削除。`scheduler.py` が実行する |
| 作成者 | `can_delete`（session の値） | 列なし | ルームを作成したブラウザ session。docstring では「所有者」。アカウントの概念は無く、削除権限は session の `can_delete` で判定する（FSQR は入室時の ID の一致も確認する） |
| 参加者 | — | 列なし | ルームに入った利用者全般（作成者を含む）。閲覧者数は `presence.py` |
| タスク | item | `task_item` | 画面は「タスク」、コードと DB は item |
| 未着手 / 進行中 / 完了 | `board_status` = `todo` / `doing` / `done` | `task_item.board_status` | 3 列の固定値（`models.py` の `Literal`） |
| 優先度（高 / 通常 / 低） | `priority` = `high` / `normal` / `low` | `task_item.priority` | 既定は `normal` |
| タグ | tag | `task_tag`、`task_item_tag` | Task の分類はタグだけで行い、カテゴリという概念は使わない |

## 状態遷移

ルームの `status` は次のように遷移します。

```text
FSQR / Group（ファイル実体を持つ）
  active ──作成者の削除 / 管理画面からの削除 / 保存期間の経過──▶ deleting ──ファイル削除に成功──▶ deleted
                                                                   └ 失敗: deleting のまま残し、scheduler が再試行

Note / Task（DB だけで完結する）
  active ──作成者の削除──▶ deleted
  active ──保存期間の経過──▶ expired
```

- 削除しても行は tombstone として残ります。消えるのはファイル、ノート本文、タスクとタグで、
  行に残る値（FSQR の `original_filename` や `secure_id` など）は削除されません。Group / Note /
  Task は `room_id` の一意制約があるため、削除済みのルームID は再利用されず、古い session が
  作り直された別のルームへ入ることもありません。
- 「有効なルーム」は `status = 'active'` かつ `expires_at > NOW()` です。Group / Note / Task は
  `room_repository.py` の `RoomTable.active_predicate` で判定します。FSQR は route 側の
  `_get_active_data`（`FSQR/fsqr_app.py`）が status と期限を判定し、期限切れならアクセス時に
  削除します。共有URL の経路は status を見ず、削除時の共有リンクの失効に頼っています。
- 状態の書き換えは data 層の関数だけで行い、route やテンプレートで `status` を書き換えません。
  遷移元を限定する場合は条件付き UPDATE（`WHERE status = ...`）にします。FSQR / Group の削除は
  この形ですが、Note / Task の `remove_room` は遷移元を限定していません。
- Note の期限切れは `Note/note_realtime.py` の `publish_room_expired` で共同編集の接続へ通知します。
- 状態値を追加・変更するときは、旧コードが知らない値を読んでも壊れないか（Blue-Green の共存）、
  scheduler の対象条件、`db_init/create_tables.sql`、この図を同じ変更で確認・更新します。

タスクの `board_status` は 3 つの値を自由に移動でき、並び順は `position` で持ちます。同時更新は
`task_item.version` で検出し、古い版からの更新・削除は競合として扱います。

## 業務ルールの置き場所

業務ルールは次の場所に集約し、route・テンプレート・静的 JS の条件分岐に複製しません。
クライアント側の検証は操作性のための重複であり、判定の正はサーバー側に置きます。現状は
route 側に残っている判定もあります（FSQR の有効判定、Task のタスク件数・タグ件数、Note の
本文長）。新しい判定は route 側へ足さず、既存の判定を移すのはその変更の目的に含まれる場合だけに
します。

| ルール | 置き場所 |
| --- | --- |
| ルームID・パスワード・保存期間・タスク項目の入力値 | `models.py` の Pydantic モデルと検証関数、上限値は `settings.py` |
| ルームID の生成と重複時の再試行 | `room_credentials.py`、`room_create.py` |
| ルームが有効か | `room_repository.py`（FSQR は `FSQR/fsqr_app.py` に残る） |
| 入室済みか・削除できるか | `room_access.py`、`room_session.py` と、Group は `Group/group_common.py`、Note / Task は `*_access.py`（Task は `Task/task_authorize.py` も）、FSQR は `FSQR/fsqr_app.py` |
| 状態遷移と削除手順 | 各サービスの `*_data.py`、共通の骨格は `room_delete.py` / `room_cleanup.py` |
| アップロード件数・合計サイズの上限 | `settings.py` の値と `file_validation.py` |
| 失敗回数・操作頻度の制限 | `rate_limit.py` |
| タスクの同時更新の競合 | `Task/task_data.py` の `version` 比較 |

識別子で追跡するもの（ルーム、FSQR のアップロード、タスク、タグ）と、値そのものに意味が
あるもの（ルームID の形式、パスワード、保存期間、日付、優先度）を区別して考えます。後者は
専用のクラスを増やさず、`models.py` の検証関数や Pydantic のフィールドとして 1 か所に定義し、
各サービスから再利用します。
