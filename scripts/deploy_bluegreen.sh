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
#   3. nginx の upstream 内 `down` を新しい色へ付け替えて reload（アトミック切替）
#   4. scheduler を最新コードへ更新（無停止対象外のバックグラウンドジョブ）
#   5. 旧コンテナを drain して停止
#
# 失敗時（新コンテナが healthy にならない / nginx -t が通らない）は切替を行わず、
# 現行の色を生かしたまま中断するため、サービスは停止しない。
#
# 前提:
#   - db / redis / scheduler は既に起動済み（infra ブートストラップ参照）
#   - デプロイ済みの fs-qr.conf（NGINX_SITE_CONF）に blue(5000)/green(5030) の
#     両 server が記載され、待機側が `down` でマークされている
#   - 実行ユーザが `sudo cp` / `sudo nginx` を（できれば NOPASSWD で）実行できる
#
# 環境変数で調整可:
#   REPO_DIR / NGINX_SITE_CONF / HEALTH_TIMEOUT(秒) / DRAIN_SECONDS(秒)
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/kota/fs-qr}"
# デプロイ済み（/etc/nginx 配下）の fs-qr.conf のパス。環境に合わせて上書きする。
NGINX_SITE_CONF="${NGINX_SITE_CONF:-/etc/nginx/sites-available/fs-qr.conf}"
STATE_DIR="${STATE_DIR:-$REPO_DIR/.deploy}"
ACTIVE_FILE="$STATE_DIR/active_color"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"
DRAIN_SECONDS="${DRAIN_SECONDS:-15}"

cd "$REPO_DIR"
mkdir -p "$STATE_DIR"

log() { printf '[deploy %(%H:%M:%S)T] %s\n' -1 "$*"; }

# --- 現在の色から、これから入れ替える色を決める ---------------------------------
# active_port = これから流す色 / standby_port = `down` にする色
current_color="$(cat "$ACTIVE_FILE" 2>/dev/null || echo none)"
case "$current_color" in
  blue)  target_color=green; target_port=5030; standby_port=5000 ;;
  green) target_color=blue;  target_port=5000; standby_port=5030 ;;
  *)     target_color=blue;  target_port=5000; standby_port=5030 ;;  # 初回は blue
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

# --- 3. nginx の upstream 内 `down` を付け替えてアトミック切替 -------------------
# fs-qr.conf の upstream 両 server 行に対し、active 側の `down` を外し standby 側へ付ける。
# 反映前にバックアップを取り、nginx -t 失敗時は元に戻して中断する（無停止維持）。
log "switching nginx upstream: active=127.0.0.1:$target_port, standby(down)=127.0.0.1:$standby_port"
tmp_conf="$(mktemp)"
bak_conf="$STATE_DIR/nginx_site.bak"
sudo cat "$NGINX_SITE_CONF" | sed -E \
  -e "s|^([[:space:]]*)server[[:space:]]+127\.0\.0\.1:${target_port}([[:space:]]+down)?[[:space:]]*;.*$|\1server 127.0.0.1:${target_port};        # active|" \
  -e "s|^([[:space:]]*)server[[:space:]]+127\.0\.0\.1:${standby_port}([[:space:]]+down)?[[:space:]]*;.*$|\1server 127.0.0.1:${standby_port} down;   # standby|" \
  > "$tmp_conf"
sudo cp "$NGINX_SITE_CONF" "$bak_conf"
sudo cp "$tmp_conf" "$NGINX_SITE_CONF"
rm -f "$tmp_conf"
if ! sudo nginx -t; then
  log "ERROR: nginx config test failed; restoring previous conf. $current_color stays live."
  sudo cp "$bak_conf" "$NGINX_SITE_CONF"
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
