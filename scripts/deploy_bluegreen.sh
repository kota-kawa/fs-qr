#!/usr/bin/env bash
#
# Blue-Green 無停止デプロイ
# ===========================
#   blue  = 127.0.0.1:5000  (compose service: web-blue,  profile: blue)
#   green = 127.0.0.1:5030  (compose service: web-green, profile: green)
#
# 流れ:
#   1. 現在「非アクティブ」な色を最新コードでビルド＆起動（db/redis は触らない）
#   2. その色の healthcheck が healthy になるまで待機（無停止の最重要ゲート）
#   3. nginx のアクティブ backend を新しい色へ書き換えて reload（アトミック切替）
#   4. scheduler を最新コードへ更新（無停止対象外のバックグラウンドジョブ）
#   5. 旧コンテナを drain して停止
#
# 失敗時（新コンテナが healthy にならない / nginx -t が通らない）は切替を行わず、
# 現行の色を生かしたまま中断するため、サービスは停止しない。
#
# 前提:
#   - db / redis / scheduler は既に起動済み（infra ブートストラップ参照）
#   - /etc/nginx/fsqr_active_backend.conf が存在し fs-qr.conf が include 済み
#   - 実行ユーザが `sudo nginx` を（できれば NOPASSWD で）実行できる
#
# 環境変数で調整可:
#   REPO_DIR / NGINX_BACKEND_FILE / HEALTH_TIMEOUT(秒) / DRAIN_SECONDS(秒)
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/kota/fs-qr}"
NGINX_BACKEND_FILE="${NGINX_BACKEND_FILE:-/etc/nginx/fsqr_active_backend.conf}"
STATE_DIR="${STATE_DIR:-$REPO_DIR/.deploy}"
ACTIVE_FILE="$STATE_DIR/active_color"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"
DRAIN_SECONDS="${DRAIN_SECONDS:-15}"

cd "$REPO_DIR"
mkdir -p "$STATE_DIR"

log() { printf '[deploy %(%H:%M:%S)T] %s\n' -1 "$*"; }

# --- 現在の色から、これから入れ替える色を決める ---------------------------------
current_color="$(cat "$ACTIVE_FILE" 2>/dev/null || echo none)"
case "$current_color" in
  blue)  target_color=green; target_port=5030 ;;
  green) target_color=blue;  target_port=5000 ;;
  *)     target_color=blue;  target_port=5000 ;;  # 初回は blue を立てる
esac
target_svc="web-$target_color"

log "current=$current_color -> deploy target=$target_color ($target_svc, :$target_port)"

# --- 1. 非アクティブ色をビルド＆起動（依存は触らない） ---------------------------
log "building $target_svc ..."
docker compose --profile "$target_color" build "$target_svc"
log "starting $target_svc ..."
docker compose --profile "$target_color" up -d --no-deps "$target_svc"

# --- 2. healthy 待ち（最重要ゲート） --------------------------------------------
cid="$(docker compose --profile "$target_color" ps -q "$target_svc")"
if [ -z "$cid" ]; then
  log "ERROR: container id for $target_svc not found"
  exit 1
fi

log "waiting for $target_svc to become healthy (timeout ${HEALTH_TIMEOUT}s) ..."
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
status=starting
while [ "$(date +%s)" -lt "$deadline" ]; do
  status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo none)"
  [ "$status" = healthy ] && break
  [ "$status" = unhealthy ] && break
  sleep 3
done

if [ "$status" != healthy ]; then
  log "ERROR: $target_svc did not become healthy (status=$status). Aborting; $current_color stays live."
  docker compose --profile "$target_color" logs --tail=80 "$target_svc" || true
  docker compose --profile "$target_color" stop "$target_svc" || true
  exit 1
fi
log "$target_svc is healthy"

# --- 3. nginx をアトミックに新しい色へ切替 --------------------------------------
log "switching nginx active backend -> 127.0.0.1:$target_port"
printf 'server 127.0.0.1:%s;\n' "$target_port" | sudo tee "$NGINX_BACKEND_FILE" >/dev/null
if ! sudo nginx -t; then
  log "ERROR: nginx config test failed; aborting switch. $current_color stays live."
  exit 1
fi
sudo nginx -s reload
echo "$target_color" > "$ACTIVE_FILE"
log "nginx now serving $target_color"

# --- 4. scheduler を最新コードへ更新（無停止対象外） ----------------------------
log "refreshing scheduler ..."
docker compose up -d --no-deps --build scheduler || log "WARN: scheduler refresh failed"

# --- 5. 旧コンテナを drain して停止 ---------------------------------------------
if [ "$current_color" = blue ] || [ "$current_color" = green ]; then
  old_svc="web-$current_color"
  log "draining old $old_svc for ${DRAIN_SECONDS}s ..."
  sleep "$DRAIN_SECONDS"
  docker compose --profile "$current_color" stop "$old_svc" || true
  log "stopped $old_svc"
fi

log "deploy complete: active=$target_color"
