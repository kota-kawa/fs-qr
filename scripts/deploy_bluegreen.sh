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
#   - 実行ユーザが `sudo -n cat` / `sudo -n cp` / `sudo -n nginx` を
#     NOPASSWD で実行できる、または root で実行する
#
# 環境変数で調整可:
#   REPO_DIR / NGINX_SITE_CONF / HEALTH_TIMEOUT(秒) / DRAIN_SECONDS(秒)
#   PRIVILEGE_CMD（既定: sudo -n） / NGINX_BIN / CP_BIN / CAT_BIN
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/var/www/fs-qr}"
# デプロイ済み（/etc/nginx 配下）の fs-qr.conf のパス。環境に合わせて上書きする。
NGINX_SITE_CONF="${NGINX_SITE_CONF:-/etc/nginx/sites-available/fs-qr.conf}"
STATE_DIR="${STATE_DIR:-$REPO_DIR/.deploy}"
ACTIVE_FILE="$STATE_DIR/active_color"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"
DRAIN_SECONDS="${DRAIN_SECONDS:-15}"

cd "$REPO_DIR"
mkdir -p "$STATE_DIR"

log() { printf '[deploy %(%H:%M:%S)T] %s\n' -1 "$*"; }

resolve_bin() {
  local name="$1"
  local fallback="$2"

  if command -v "$name" >/dev/null 2>&1; then
    command -v "$name"
  else
    printf '%s\n' "$fallback"
  fi
}

NGINX_BIN="${NGINX_BIN:-$(resolve_bin nginx /usr/sbin/nginx)}"
CP_BIN="${CP_BIN:-$(resolve_bin cp /bin/cp)}"
CAT_BIN="${CAT_BIN:-$(resolve_bin cat /bin/cat)}"

PRIVILEGE_PREFIX=()
if [ "$(id -u)" -ne 0 ]; then
  # Default to non-interactive sudo so CI fails immediately with a useful
  # message instead of hanging or failing after the new slot has started.
  # shellcheck disable=SC2206
  PRIVILEGE_PREFIX=(${PRIVILEGE_CMD:-${SUDO:-sudo -n}})
fi

run_privileged() {
  if [ "${#PRIVILEGE_PREFIX[@]}" -eq 0 ]; then
    "$@"
  else
    "${PRIVILEGE_PREFIX[@]}" "$@"
  fi
}

fail_privilege() {
  log "ERROR: cannot manage nginx non-interactively."
  log "Configure passwordless sudo for the deploy user, or run this script as root."
  log "Required commands: $CAT_BIN, $CP_BIN, $NGINX_BIN"
  log "Example sudoers entry:"
  log "  <SERVER_USER> ALL=(root) NOPASSWD: $CAT_BIN, $CP_BIN, $NGINX_BIN"
}

abort_deploy() {
  log "$*"
  return 1
}

preflight_nginx_switch() {
  local preflight_copy

  log "checking nginx switch permissions ..."

  if ! run_privileged "$CAT_BIN" "$NGINX_SITE_CONF" >/dev/null; then
    fail_privilege
    return 1
  fi

  preflight_copy="$STATE_DIR/nginx_site.preflight.$$"
  rm -f "$preflight_copy"
  if ! run_privileged "$CP_BIN" "$NGINX_SITE_CONF" "$preflight_copy"; then
    rm -f "$preflight_copy"
    fail_privilege
    return 1
  fi
  rm -f "$preflight_copy"

  if ! run_privileged "$NGINX_BIN" -t; then
    log "ERROR: existing nginx configuration is invalid or nginx cannot be tested."
    return 1
  fi
}

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
preflight_nginx_switch

tmp_conf=""
bak_conf="$STATE_DIR/nginx_site.bak"
target_started=false
switch_completed=false

on_error() {
  local exit_code=$?
  trap - ERR
  [ -n "$tmp_conf" ] && rm -f "$tmp_conf"

  if [ "$switch_completed" != true ] && [ "$target_started" = true ]; then
    log "stopping unpromoted $target_svc after failed deploy ..."
    docker compose --profile "$target_color" stop "$target_svc" || true
  fi

  exit "$exit_code"
}

trap on_error ERR

# --- 1. 非アクティブ色をビルド＆起動（依存は触らない） ---------------------------
log "building $target_svc ..."
docker compose --profile "$target_color" build "$target_svc"
log "starting $target_svc ..."
docker compose --profile "$target_color" up -d --no-deps "$target_svc"
target_started=true

# --- 2. healthy 待ち（最重要ゲート） --------------------------------------------
cid="$(docker compose --profile "$target_color" ps -q "$target_svc")"
if [ -z "$cid" ]; then
  abort_deploy "ERROR: container id for $target_svc not found"
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
  abort_deploy "ERROR: failed before nginx switch; $current_color stays live."
fi
log "$target_svc is healthy"

# --- 3. nginx の upstream 内 `down` を付け替えてアトミック切替 -------------------
# fs-qr.conf の upstream 両 server 行に対し、active 側の `down` を外し standby 側へ付ける。
# 反映前にバックアップを取り、nginx -t 失敗時は元に戻して中断する（無停止維持）。
log "switching nginx upstream: active=127.0.0.1:$target_port, standby(down)=127.0.0.1:$standby_port"
tmp_conf="$(mktemp "$STATE_DIR/nginx_site.XXXXXX")"
run_privileged "$CAT_BIN" "$NGINX_SITE_CONF" | sed -E \
  -e "s|^([[:space:]]*)server[[:space:]]+127\.0\.0\.1:${target_port}([[:space:]]+down)?[[:space:]]*;.*$|\1server 127.0.0.1:${target_port};        # active|" \
  -e "s|^([[:space:]]*)server[[:space:]]+127\.0\.0\.1:${standby_port}([[:space:]]+down)?[[:space:]]*;.*$|\1server 127.0.0.1:${standby_port} down;   # standby|" \
  > "$tmp_conf"
run_privileged "$CP_BIN" "$NGINX_SITE_CONF" "$bak_conf"
run_privileged "$CP_BIN" "$tmp_conf" "$NGINX_SITE_CONF"
rm -f "$tmp_conf"
tmp_conf=""
if ! run_privileged "$NGINX_BIN" -t; then
  log "ERROR: nginx config test failed; restoring previous conf. $current_color stays live."
  run_privileged "$CP_BIN" "$bak_conf" "$NGINX_SITE_CONF" || true
  abort_deploy "ERROR: failed before nginx reload; $current_color stays live."
fi
if ! run_privileged "$NGINX_BIN" -s reload; then
  log "ERROR: nginx reload failed; restoring previous conf. $current_color stays live."
  run_privileged "$CP_BIN" "$bak_conf" "$NGINX_SITE_CONF" || true
  run_privileged "$NGINX_BIN" -t || true
  abort_deploy "ERROR: failed before nginx switch completed; $current_color stays live."
fi
switch_completed=true
if ! printf '%s\n' "$target_color" > "$ACTIVE_FILE"; then
  log "WARN: failed to record active color in $ACTIVE_FILE; nginx is already serving $target_color"
fi
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
