#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

failures=0

info() {
  printf '[info] %s\n' "$*"
}

warn() {
  printf '[warn] %s\n' "$*" >&2
}

fail() {
  printf '[fail] %s\n' "$*" >&2
  failures=$((failures + 1))
}

if ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose plugin is not available. Install Docker Compose v2."
else
  info "Docker Compose is available."
fi

if docker compose config --quiet; then
  info "docker-compose.yml is valid."
else
  fail "docker-compose.yml is invalid."
fi

if [ -r /proc/sys/vm/overcommit_memory ]; then
  overcommit="$(cat /proc/sys/vm/overcommit_memory)"
  if [ "${overcommit}" != "1" ]; then
    warn "vm.overcommit_memory=${overcommit}. Redis may fail background saves."
    warn "For Linux hosts, run: sudo sysctl vm.overcommit_memory=1"
    warn "To persist it, add 'vm.overcommit_memory = 1' to /etc/sysctl.conf."
  else
    info "vm.overcommit_memory is enabled."
  fi
else
  warn "Cannot read /proc/sys/vm/overcommit_memory; skipping Redis host check."
fi

info "Inspecting the MySQL Docker volume without starting mysqld."
if ! docker compose run --rm --no-deps --entrypoint sh db -lc '
set -eu
datadir=/var/lib/mysql
if [ ! -d "${datadir}/mysql" ] && [ ! -e "${datadir}/mysql.ibd" ]; then
  echo "MySQL datadir appears empty; it will be initialized on first healthy start."
  exit 0
fi

if [ ! -e "${datadir}/mysql.ibd" ]; then
  echo "Missing ${datadir}/mysql.ibd. The MySQL data dictionary is incomplete." >&2
  exit 10
fi

if [ ! -r "${datadir}/mysql.ibd" ]; then
  echo "${datadir}/mysql.ibd exists but is not readable." >&2
  exit 11
fi

echo "MySQL data dictionary file is present and readable."
'; then
  fail "MySQL volume looks incomplete or unreadable. If this is disposable local data, run: docker compose down -v"
fi

if [ "${failures}" -gt 0 ]; then
  fail "Preflight finished with ${failures} problem(s)."
  exit 1
fi

info "Preflight checks passed."
