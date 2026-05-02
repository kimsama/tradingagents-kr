#!/bin/sh
set -eu

APP_USER=appuser
APP_GROUP=appuser
APP_HOME=${HOME:-/home/appuser}
TRADINGAGENTS_HOME="${APP_HOME}/.tradingagents"

ensure_owned_dir() {
    mkdir -p "$1"
    if [ "$(id -u)" = "0" ]; then
        chown -R "${APP_USER}:${APP_GROUP}" "$1"
    fi
}

if [ "$#" -eq 0 ] || [ "${1#-}" != "$1" ]; then
    set -- tradingagents "$@"
elif ! command -v "$1" >/dev/null 2>&1; then
    set -- tradingagents "$@"
fi

cache_dir=${TRADINGAGENTS_CACHE_DIR:-"${TRADINGAGENTS_HOME}/cache"}
results_dir=${TRADINGAGENTS_RESULTS_DIR:-"${TRADINGAGENTS_HOME}/logs"}
memory_log_path=${TRADINGAGENTS_MEMORY_LOG_PATH:-"${TRADINGAGENTS_HOME}/memory/trading_memory.md"}
memory_dir=$(dirname "$memory_log_path")

ensure_owned_dir "$TRADINGAGENTS_HOME"
ensure_owned_dir "$cache_dir"
ensure_owned_dir "$results_dir"
if [ "$memory_dir" != "." ] && [ -n "$memory_dir" ]; then
    ensure_owned_dir "$memory_dir"
fi

if [ "$(id -u)" = "0" ]; then
    exec setpriv --reuid="${APP_USER}" --regid="${APP_GROUP}" --init-groups -- "$@"
fi

exec "$@"
