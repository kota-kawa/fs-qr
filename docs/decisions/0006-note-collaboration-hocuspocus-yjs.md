# ADR-0006: Note共同編集をHocuspocus / Yjsへ移行する

- 状態: 採用
- 日付: 2026-08-21
- 対象: `hocuspocus/`、`Note/`、`static/js/note_room_realtime/`
- 置換する判断: [ADR-0003](0003-note-realtime-redis-pubsub.md)

## 背景

従来のNoteは、Pythonとブラウザに独自のversion管理・差分merge・self-edit待機を持っていた。
この方式は競合経路が多く、クライアントとサーバーの状態機械を同時に保守する必要がある。
複数worker間の配信はRedis Pub/Subで補っていたが、競合解決自体は独自実装だった。

## 判断

共同編集プロトコルと競合解決をYjs CRDTへ移し、Hocuspocus v4をNode sidecarとして運用する。

- ブラウザはローカルbundleの`@hocuspocus/provider`とYjsを使い、nginxの`/yjs`へ接続する。
- Hocuspocus instance間のYjs updateとstore lockは`@hocuspocus/extension-redis`で共有する。
- `note_content.yjs_state`へbinary stateを保存し、既存の`content`には最新plain textをmirrorする。
  TXT/PDF出力、旧版への緊急rollback、運用上の参照はこのmirrorを使える。
- 既存行の`yjs_state`はNULLを許容し、最初の接続で`content`から遅延変換する。migrationは
  expand-onlyとし、既存本文を書き換えない。
- 接続時は、短寿命・room限定HMAC tokenに加えて、同一Origin、StarSessionsのRedis session内
  `note_room_access`、DB上のroom有効期限を検証する。tokenだけでは接続を許可しない。
- 期限切れ・削除は既存の`note:room:{room_id}` control eventで全sidecarの接続を閉じる。
  eventを失っても、次回storeでroomが無効なら更新を拒否して接続を閉じる。
- 旧HTTP POST同期APIは410を返す。旧WebSocket router、独自merge、`diff-match-patch`は削除する。

## 理由

Yjsは操作をCRDTとして統合するため、独自のversion競合分岐や「どちらを正とするか」の
上書き判断をアプリケーションから除去できる。Hocuspocusは認証、永続化hook、Redisによる
複数instance同期を提供し、WebSocket serverを独自実装する範囲を小さくできる。

## 影響

- Node sidecarがNote編集の必須依存になる。HTTP画面やplain text参照が動いていても、sidecar、
  Redis、MySQLのいずれかが利用できなければ新しい編集sessionは確立しない。
- `SECRET_KEY`はPythonとHocuspocusで共用し、`PUBLIC_SITE_URL`が許可Originになる。
- Yjs updateはat-least-oneのHTTP保存ではなくCRDT同期であり、500ms debounce後にMySQLへ保存する。
- sidecar再起動時はproviderが自動再接続する。デプロイでsidecarを更新すると短い再接続表示が出る。
- 旧版へrollbackした場合も`content`は読み書きできる。新版へ戻した際、保存済みYjs stateと
  plain textが異なればplain textを正としてYjs stateを再生成する。旧版と新版から同一roomへ
  同時に書き込ませないよう、nginx切替後に旧webをdrainする。

## 検証

Node testでtoken・Origin・session access・2クライアントの収束とstate保存を確認する。
Python testでroom画面、legacy API、期限切れcontrol eventを確認し、Docker smoke testで
Hocuspocus、Redis、MySQL、nginx接続境界を確認する。
