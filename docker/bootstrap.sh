#!/bin/bash
# 首次初始化：建站点 + 安装本 App + 生成演示数据
set -euo pipefail

BENCH_DIR=/home/frappe/frappe-bench
SITE=demo.local

cd "$BENCH_DIR"

bench new-site "$SITE" --mariadb-root-password root --admin-password admin \
  --mariadb-host mariadb --redis-cache "redis://redis:6379/1" \
  --redis-queue "redis://redis:6379/2" --redis-socketio "redis://redis:6379/3"

# 把挂载的 App 目录软链进 bench 的 apps 下
ln -sfn /workspace "$BENCH_DIR/apps/user_growth"
bench --site "$SITE" install-app user_growth
bench set-config -g default_site "$SITE"

echo "初始化完成：http://localhost:8000  (Administrator / admin)"
