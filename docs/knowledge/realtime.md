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
WebSocket 自体は各 worker の `GroupRoomHub` で保持し、ファイル更新の `files_updated` と
ルーム削除の `room_closed` は Redis channel `group:room:{room_id}` を通じて他 worker に
配信します。接続の room / instance 集計も Redis に記録し、shutdown 時に自身の残骸を
掃除します。Redis 障害時は同一プロセス通知とクライアントのポーリングに縮退します。

## 変更時の不変条件

- 接続前に room の有効性、session access、CSRF を確認する。
- disconnect と送信エラーの両方で接続を hub から除去する。
- Note の更新 payload は `request_id`、version、status を壊さない。競合時は client の
  内容を黙って上書きせず、既存の merge / conflict 応答を使う。
- room 期限切れ時は DB の状態だけでなく、接続中クライアントへの通知・close を確認する。
- Redis を使う処理では、接続失敗、pub/sub 再開、shutdown cleanup をテストする。
- Group の更新 payload は `files_updated` と `room_closed` 以外を受け付けない。ルームを
  削除した場合は、全 worker の WebSocket を閉じ、ブラウザが再接続を繰り返さないことを確認する。

## 調査の順序

1. ブラウザの WebSocket close code、network payload、session cookie の有無を確認する。
2. `tests/test_note_ws.py` / `tests/test_group_realtime.py` の CSRF と disconnect の期待値を確認する。
3. Note / Group ともに `get_redis()`、pub/sub task、`INSTANCE_ID` ごとの cleanup を確認する。
4. Group では、更新 endpoint が `notify_group_files_updated()` を呼び、Redis channel
   `group:room:{room_id}` と各 worker の hub に同じイベントが届いているかを確認する。
5. DB の version / room status、Redis の該当 channel / key、アプリログを同じ時刻帯で照合する。

## 代表的な検証

```bash
python3 -m pytest tests/test_note_realtime.py tests/test_note_ws.py -q
python3 -m pytest tests/test_group_realtime.py -q
```

複数クライアント・再接続・Redis 再起動の実動作は、単体テストだけでは保証できません。
Docker または実 Redis を使った手動 smoke test ができない場合は、その未実施を明記します。
