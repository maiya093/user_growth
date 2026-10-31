#!/bin/bash
# 首次初始化（一次性容器）：建站点 → 安装本 App → 生成演示数据
# 由 docker compose run --rm init 调用。要重建环境用 docker compose down -v
set -euo pipefail

BENCH_DIR=/home/frappe/frappe-bench
SITE="${SITE_NAME:-demo.local}"
DB_HOST="${DB_HOST:-mariadb}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:-root}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
SRC=/workspace/user_growth

cd "$BENCH_DIR"

echo "==> 1/5 检查站点是否已存在"
if [ -d "$BENCH_DIR/sites/$SITE" ]; then
	echo "    站点 $SITE 已存在，跳过建站"
else
	echo "==> 2/5 建站 $SITE（utf8mb4，约 2-4 分钟）"
	bench new-site "$SITE" \
		--mariadb-root-password "$DB_ROOT_PASSWORD" \
		--admin-password "$ADMIN_PASSWORD" \
		--mariadb-host "$DB_HOST" \
		--no-mariadb-socket
fi

echo "==> 3/5 把 App 源码链入 bench"
if [ -e "$BENCH_DIR/apps/user_growth" ]; then
	echo "    已存在，跳过"
else
	ln -sfn "$SRC" "$BENCH_DIR/apps/user_growth"
fi

echo "==> 4/5 安装 App（触发 after_install：建角色 + 生成演示数据）"
if bench --site "$SITE" list-apps 2>/dev/null | grep -qx "user_growth"; then
	echo "    user_growth 已安装，跳过"
else
	bench --site "$SITE" install-app user_growth
fi

echo "==> 5/5 设置默认站点并清缓存"
bench set-config -g default_site "$SITE"
bench --site "$SITE" clear-cache || true

echo
echo "初始化完成 → http://localhost:8000   账号 Administrator / ${ADMIN_PASSWORD}"
echo "若演示数据为空，可手动补："
echo "  docker compose exec frappe bench --site $SITE execute user_growth.setup.demo_data.run"
