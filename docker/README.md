# 容器化运行（可选）

不想装 bench 时，可用 Docker 起一个可运行的 Frappe v15 环境。

```bash
cd docker
docker compose up -d mariadb redis
docker compose run --rm init     # 首次初始化，约 5-10 分钟
docker compose up -d frappe
```

访问 `http://localhost:8000`，账号 `Administrator` / 密码 `admin`。

> 仅用于快速体验；正式验证请用本地 bench 安装（见根目录 README 第二节）。
