# ADR-0003: Note realtime は Redis pub/sub を使う

- 状態: 採用
- 対象: `Note/note_ws.py`、`Note/note_realtime.py`、`Note/note_sync.py`

## 背景

Note は複数の Gunicorn worker / web コンテナから同じ room に接続されます。プロセス内の
WebSocket set だけでは、ある worker の編集を別 worker のクライアントへ通知できません。

## 判断

各 worker はローカルの `RoomHub` で直接接続を管理し、更新 payload と期限切れ通知を
`note:room:{room_id}` に publish します。他 worker は pub/sub を購読して自身の接続へ
broadcast します。接続の room / instance 集計も Redis に記録し、shutdown 時に自分の
instance の残存接続を掃除します。

## 理由

- WebSocket 接続そのものを Redis に置かず、低遅延の送信はメモリで行える。
- Blue-Green の一時的な二重稼働でも Note の更新通知を共有できる。
- instance key により、プロセス終了後の接続数残骸を掃除できる。

## 影響

- Redis 障害時は同一プロセス限定の動作へ縮退し、複数 worker 同期は保証されない。
- 接続時の CSRF、room access、version / merge 応答を pub/sub の前後で壊してはいけない。
- 接続、切断、再接続、複数クライアント、Redis 不在を変更時の検証範囲に含める。
