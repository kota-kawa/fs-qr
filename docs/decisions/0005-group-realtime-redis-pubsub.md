# ADR-0005: Group realtime は Redis pub/sub を使う

- 状態: 採用
- 対象: `Group/group_realtime.py`、`Group/group_data.py`、`app.py`
- 関連: ADR-0002 の Group がプロセス内 hub のみだった制約を置き換える

## 背景

Group の WebSocket は worker ごとのメモリにしか接続を保持していなかったため、アップロード
または削除を処理した worker と別の worker に接続した利用者へ `files_updated` が届きません
でした。Blue-Green の一時的な並行稼働でも同じ問題が起こります。

## 判断

WebSocket オブジェクトは各 worker のローカル `GroupRoomHub` で保持し続け、更新とルーム閉鎖
イベントを Redis channel `group:room:{room_id}` に publish します。各 worker は
`group:room:*` を購読し、他 instance からのイベントだけをローカル接続へ fanout します。
接続の room / instance 集計も Redis Set に記録し、起動時と shutdown 時にその instance の
残骸を掃除します。

## 理由

- WebSocket 接続を Redis に直列化せず、既存の低遅延なローカル送信を維持できる。
- 複数 Gunicorn worker と Blue-Green の両スロットに、同じ room のイベントを配信できる。
- `room_closed` を共有して、削除済み room のブラウザが再接続を繰り返すことを防げる。

## 影響

- Redis pub/sub は at-most-once のため、クライアントは既存のファイル一覧再取得とポーリングを
  補完手段として維持する。
- Redis 障害中は同一 worker に限定して動作する。HTTP のアップロード・削除は通知失敗だけで
  失敗させず、購読 task は Redis 復旧後に再接続を試みる。
- 新しい realtime event は payload の許可リスト、WebSocket CSRF、room access、接続・切断・
  shutdown cleanup の検証を同時に満たす必要がある。
