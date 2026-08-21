# リアルタイム機能の運用知識

## 接続モデル

### Note

`/ws/note/{room_id}` は `Note/note_ws.py` が入口です。接続時に room access と WebSocket
CSRF を確認し、初期本文を送ります。保存は `note_sync.py` の version / merge 処理を通し、
同一プロセスの接続には `RoomHub`、別プロセスの接続には Redis channel
`note:room:{room_id}` の pub/sub で更新を配信します。

`Note/note_realtime.py` は Redis 上で room connection と instance connection を追跡し、
shutdown 時に自身の接続を掃除します。Redis が使えない場合は同一プロセスに限定された
動作になるため、複数 worker の同期をテストで暗黙に保証しないでください。

### Group

`/ws/group/{room_id}` は `Group/group_routes_ws.py` と `Group/group_realtime.py` が入口です。
ファイル更新時の `files_updated` は `GroupRoomHub` 内の同じプロセスの WebSocket にだけ
broadcast されます。Note と異なり、Group に Redis pub/sub の横断配信はありません。

## 変更時の不変条件

- 接続前に room の有効性、session access、CSRF を確認する。
- disconnect と送信エラーの両方で接続を hub から除去する。
- Note の更新 payload は `request_id`、version、status を壊さない。競合時は client の
  内容を黙って上書きせず、既存の merge / conflict 応答を使う。
- room 期限切れ時は DB の状態だけでなく、接続中クライアントへの通知・close を確認する。
- Redis を使う処理では、接続失敗、pub/sub 再開、shutdown cleanup をテストする。
- Group の multi-worker 同期を必要にする変更は、単なる修正ではなく配信方式の変更として
  decision record を追加する。

## 調査の順序

1. ブラウザの WebSocket close code、network payload、session cookie の有無を確認する。
2. `tests/test_note_ws.py` / `tests/test_group_realtime.py` の CSRF と disconnect の期待値を確認する。
3. Note なら `get_redis()`、pub/sub task、`INSTANCE_ID` ごとの cleanup を確認する。
4. Group なら、クライアントが同じ worker に接続しているか、更新 endpoint が同じ hub の
   `broadcast` を呼んでいるかを確認する。
5. DB の version / room status、Redis の該当 channel / key、アプリログを同じ時刻帯で照合する。

## 代表的な検証

```bash
python3 -m pytest tests/test_note_realtime.py tests/test_note_ws.py -q
python3 -m pytest tests/test_group_realtime.py -q
```

複数クライアント・再接続・Redis 再起動の実動作は、単体テストだけでは保証できません。
Docker または実 Redis を使った手動 smoke test ができない場合は、その未実施を明記します。
