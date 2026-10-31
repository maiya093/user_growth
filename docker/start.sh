#!/bin/bash
# 启动 Web 服务（开发模式：web + socketio + watch + schedule + worker 全起）
set -euo pipefail

BENCH_DIR=/home/frappe/frappe-bench
SITE="${SITE_NAME:-demo.local}"
DB_HOST="${DB_HOST:-mariadb}"

cd "$BENCH_DIR"

# 多容器环境下 Redis / DB 走服务名，配置在共同配置里，避免依赖镜像默认值
bench set-config -g db_host "$DB_HOST"
bench set-config -g redis_cache redis://redis:6379/1
bench set-config -g redis_queue redis://redis:6379/2
bench set-config -g redis_socketio redis://redis:6379/3
bench set-config -g default_site "$SITE"

echo "==> 启动 bench（http://localhost:8000）"
exec bench start
