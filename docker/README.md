# 容器化运行（可选，不装 bench 也能跑）

不想在本机装 Python / Node / MariaDB 时，用 Docker 起一个完整的 Frappe v15 + 本 App 环境。

---

## 前置：装 Docker Desktop

| 平台 | 下载 | 注意 |
|---|---|---|
| Windows | <https://www.docker.com/products/docker-desktop/> | 安装时勾选 **Use WSL 2**；装完重启电脑；首次启动要等鲸鱼图标变绿 |
| macOS | 同上 | Apple 芯片选 Apple Silicon 版本 |

装好验证（**新开一个终端**）：

```bash
docker --version
docker compose version      # 必须能输出版本号，说明 compose v2 已就绪
docker ps                   # 不报错 = 引擎已运行
```

国内网络拉镜像慢，建议先配镜像加速：Docker Desktop → Settings → Docker Engine，在 `registry-mirrors` 里加
`https://docker.m.daocloud.io`，点 Apply & Restart。

---

## 一、拿代码

```bash
git clone https://github.com/maiya093/user_growth.git
cd user_growth/docker
```

> 后面所有命令都在 `user_growth/docker` 目录下执行（compose 会自动找同级目录的 compose 文件）。

---

## 二、三步跑起来

### 第 1 步：起数据库、缓存，并构建 bench 镜像

```bash
docker compose up -d mariadb redis
docker compose build bench-base    # 构建 Frappe v15 环境镜像，约 10-15 分钟（只需一次）
docker compose ps                  # mariadb / redis 都应是 running (healthy)
```

说明：`bench-base` 会在镜像里跑 `bench init`，把 Python 环境、Frappe v15 源码、Node 依赖全部装好并缓存进镜像。
**这一步只做一次**，之后每次启动都是秒级。首次会下载基础镜像与 pip 依赖，视网速可能更久，
网络差时可先配镜像加速（见上方「前置」）。

### 第 2 步：初始化（只需一次，约 3-5 分钟）

```bash
docker compose run --rm init
```

这一步会依次：建站点 `demo.local` → 链接 App 源码 → 安装 App（自动建角色、生成 24 个月演示数据）。
脚本是幂等的，重复执行只会跳过已完成的部分，不会破坏数据。

看到下面这行就成功了：

```
初始化完成 → http://localhost:8000   账号 Administrator / admin
```

### 第 3 步：启动 Web 服务

```bash
docker compose up -d frappe
docker compose logs -f frappe      # 看到 127.0.0.1:8000 就可以 Ctrl+C 退出日志
```

浏览器打开 <http://localhost:8000>，登录 **Administrator / admin**。

---

## 三、进到页面

登录后：

| 要看什么 | 怎么进 |
|---|---|
| 数据大屏 | 搜索框输入 `用户增长数据大屏`，或直接访问 <http://localhost:8000/app/user-growth-dashboard> |
| 分析报表 | <http://localhost:8000/app/query-report/User Growth Analysis> |
| 单据列表 | <http://localhost:8000/app/user-service-record> |
| 工作区总入口 | 搜索框输入 `用户增长` |

大屏右上角有**全屏**按钮，适合投屏演示。

---

## 四、常用命令

```bash
docker compose stop frappe                 # 停 Web 服务（数据保留）
docker compose up -d frappe                # 再启动
docker compose logs -f frappe              # 看日志
docker compose exec frappe bench --site demo.local execute user_growth.setup.demo_data.run   # 补演示数据
docker compose down                        # 停止全部容器（数据卷保留）
docker compose down -v                     # 连数据一起删，彻底重置（下次要重跑 init）
```

---

## 五、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop 没启动 | 打开 Docker Desktop，等鲸鱼图标变绿再执行 |
| `docker compose` 报 `unknown command` | 装的是旧版 docker-compose | 升级 Docker Desktop（自带 compose v2） |
| 第 1 步 `build` 卡在 apt / pip | 国内直连官方源慢 | 给 Docker Desktop 配镜像加速；或改用国内 apt / pip 源（可改 Dockerfile 中的源地址） |
| `build` 报 `nodejs` / `npm` 版本过旧 | Ubuntu 22.04 自带 node 12 | 已改用 npm 安装；若仍失败，在 Dockerfile 里换用 NodeSource 源装 node 18 |
| `init` 提示站点已存在 | 之前初始化过 | 正常，可直接做第 3 步；要重建则 `docker compose down -v` 后重来 |
| 8000 端口被占用 | 本机已有程序占用 | 改 compose 里 `ports: "8080:8000"`，访问 `http://localhost:8080` |
| 页面 500，日志提示连不上 redis | 容器刚起，服务未就绪 | `docker compose restart frappe`，等 20 秒再刷 |
| 登录后看不到大屏入口 | 角色未分配 | Administrator 本身就是 System Manager，可见；普通用户需分配 `Growth Manager` |

---

---

## 六、这个方案做了什么（便于排查）

| 组件 | 镜像 | 作用 |
|---|---|---|
| `bench-base` | 由 `Dockerfile` 构建 | 一次性跑完 `bench init`，产出含 Frappe v15 的镜像 |
| `mariadb` | `mariadb:10.6` | 数据库，启动参数已设 `utf8mb4`（Frappe 必需） |
| `redis` | `redis:alpine` | cache / queue / socketio 三个库共用 |
| `init` | 复用 bench 镜像 | 建站 + `install-app` + 生成演示数据，跑完即退出 |
| `frappe` | 复用 bench 镜像 | `bench start`，暴露 8000 端口 |

> 两个数据卷 `bench_sites` / `bench_apps` 让 `init` 建好的站点被 `frappe` 服务直接复用。
> 仓库以**只读**方式挂在 `/workspace`，不会污染镜像内的 Python 环境。

> 本方案用于快速体验。要完整复现开发环境（含 `bench build`、跑单测），请参考根目录 README 第二节的 bench 安装方式。
