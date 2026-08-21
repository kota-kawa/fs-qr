# リアルタイム機能の運用知識

## 接続モデル

### Note

nginxの`/yjs`は`hocuspocus/server.js`へproxyし、Hocuspocus v4がYjs文書を多重化します。
ブラウザbundleは`static/js/note_room_realtime/yjs-collaboration.js`です。Yjs updateはRedis
extensionを介して全Hocuspocus instanceへ伝わり、500ms debounce後に`note_content.yjs_state`
とplain textの`content`へ保存されます。

接続はroom限定HMAC tokenだけでなく、`PUBLIC_SITE_URL`と一致するOrigin、StarSessionsの
Redis recordにある`note_room_access`、DB上のactive statusと期限をすべて検証します。
ルーム削除・期限切れは`Note/note_realtime.py`が`note:room:{room_id}`へcontrol eventをpublishし、
sidecarが該当接続を閉じます。Redisは同期、session認可、期限切れ通知に必須で、メモリだけの
共同編集へfallbackしません。

### Group

`/ws/group/{room_id}` は `Group/group_routes_ws.py` と `Group/group_realtime.py` が入口です。
WebSocket 自体は各 worker の `GroupRoomHub` で保持し、ファイル更新の `files_updated` と
ルーム削除の `room_closed` は Redis channel `group:room:{room_id}` を通じて他 worker に
配信します。接続の room / instance 集計も Redis に記録し、shutdown 時に自身の残骸を
掃除します。Redis 障害時は同一プロセス通知とクライアントのポーリングに縮退します。

## 変更時の不変条件

- 接続前にroomの有効性とsession accessを確認する。GroupはWebSocket CSRF、Noteは
  同一Originと短寿命tokenも検証する。
- disconnect と送信エラーの両方で接続を hub から除去する。
- Noteの競合解決を独自version/mergeへ戻さず、Yjs document updateとして扱う。
- `content`と`yjs_state`を同じstoreで更新し、plain text mirrorをexport/rollback用に保つ。
- room 期限切れ時は DB の状態だけでなく、接続中クライアントへの通知・close を確認する。
- Redis を使う処理では、接続失敗、instance間収束、pub/sub再開、store lock、
  shutdown cleanupをテストする。
- Group の更新 payload は `files_updated` と `room_closed` 以外を受け付けない。ルームを
  削除した場合は、全 worker の WebSocket を閉じ、ブラウザが再接続を繰り返さないことを確認する。

## 調査の順序

1. ブラウザのWebSocket status / close code、network payload、session cookieの有無を確認する。
2. Noteは`docker compose ps hocuspocus`とsidecar log、Redis、`yjs_state`を同じ時刻で確認する。
3. `PUBLIC_SITE_URL`と実際のOrigin、`starsessions.<session-id>`のroom accessを照合する。
4. Groupは`get_redis()`、pub/sub task、`INSTANCE_ID`ごとのcleanupを確認する。
5. Group では、更新 endpoint が `notify_group_files_updated()` を呼び、Redis channel
   `group:room:{room_id}` と各 worker の hub に同じイベントが届いているかを確認する。
6. DB の room status、Redis の該当 channel / key、アプリログを同じ時刻帯で照合する。

## 代表的な検証

```bash
python3 -m pytest tests/test_note_collaboration.py tests/test_note_realtime.py -q
(cd hocuspocus && npm ci && npm test && npm run build:client)
python3 -m pytest tests/test_group_realtime.py -q
```

複数sidecar、再接続、Redis再起動、MySQLからの復元は単体テストだけでは保証できません。
変更時はDocker smoke testを行い、実施できない項目は明記します。
