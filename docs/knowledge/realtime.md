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
ファイル更新時の `files_updated` は `GroupRoomHub` 内の同じプロセスの WebSocket にだけ
broadcast されます。Note と異なり、Group に Redis pub/sub の横断配信はありません。

## 変更時の不変条件

- 接続前にroomの有効性、session access、同一Origin、短寿命tokenを確認する。
- Noteの競合解決を独自version/mergeへ戻さず、Yjs document updateとして扱う。
- `content`と`yjs_state`を同じstoreで更新し、plain text mirrorをexport/rollback用に保つ。
- room期限切れ時はDBの状態だけでなく、接続中クライアントのcloseを確認する。
- Redisを使う処理では、接続失敗、instance間収束、store lock、shutdown cleanupを確認する。
- Groupのmulti-worker同期を必要にする変更は、単なる修正ではなく配信方式の変更として
  decision recordを追加する。

## 調査の順序

1. ブラウザの`/yjs` WebSocket status、Origin、session cookieの有無を確認する。
2. Noteなら`docker compose ps hocuspocus`とsidecar log、Redis、`yjs_state`を同じ時刻で確認する。
3. `PUBLIC_SITE_URL`と実際のブラウザOrigin、`starsessions.<session-id>`のroom accessを照合する。
4. Groupなら、クライアントが同じworkerに接続しているか、更新endpointが同じhubの
   `broadcast`を呼んでいるかを確認する。

## 代表的な検証

```bash
python3 -m pytest tests/test_note_collaboration.py tests/test_note_realtime.py -q
(cd hocuspocus && npm ci && npm test && npm run build:client)
python3 -m pytest tests/test_group_realtime.py -q
```

複数sidecar、再接続、Redis再起動、MySQLからの復元は単体テストだけでは保証できません。
変更時はDocker smoke testを行い、実施できない項目は明記します。
