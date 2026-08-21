# ADR-0002: web を Blue-Green で切り替える

- 状態: 採用
- 対象: `docker-compose.yml`、`fs-qr.conf`、`scripts/deploy_bluegreen.sh`

## 背景

単一 web コンテナを作り直す方式では、切替中に nginx の upstream が利用できず 502 が
発生します。大容量 upload、session、DB、realtime を含むサービスのため、アプリを
停止させずに新しいイメージを検証してから切り替える必要があります。

## 判断

web を host port 5000 の blue と 5030 の green に分け、非アクティブ側を build・起動し、
healthcheck が通った後に nginx upstream の `down` を付け替えて reload します。DB、Redis、
scheduler は共有し、scheduler は一つだけ動かします。

## 理由

- 新コンテナの失敗を nginx 切替前に検出できる。
- 切替失敗時も現行色を生かしたまま中断できる。
- 共有 Redis によって session、cache、rate limit、presence、Note の cross-process
  state を色をまたいで保持できる。

## 影響

- nginx 設定の読み取り・バックアップ・検証・reload に非対話 sudo が必要。
- 旧コンテナ停止時、進行中の大容量 upload は graceful timeout の影響を受ける。
- Group の WebSocket hub はプロセス内実装で、共有 Redis による cross-worker broadcast
  を提供しない。Note の cross-process 同期とは別の制約として扱う。
- 詳細な初回設定、切替、rollback は [Blue-Green 運用手順](../blue-green-deploy.md)を正とする。
