# 推送到 GitHub / Gitee —— 操作手册

> 仓库已就绪：`/workspace/user_growth`，分支 `main`，10 个语义化提交，工作区干净，**无需再初始化**。
> 你只需要「建远程仓库 → 加 remote → push」三步。

---

## 零、推送前 30 秒检查

```bash
cd /workspace/user_growth

git status            # 应为 "nothing to commit, working tree clean"
git log --oneline     # 10 条提交
git remote -v         # 目前为空，属正常
```

**提交作者**当前是 `Interview Demo <demo@example.com>`。如果想让 GitHub 头像正确归属到你本人，
务必先改成你账号绑定的邮箱（**否则贡献图不亮**）：

```bash
git config user.name  "你的名字"
git config user.email "你的GitHub邮箱"

# 把历史 10 条提交的作者一并改掉（仓库尚未公开，安全）
git rebase -r --root --exec 'git commit --amend --no-edit --reset-author'
```

---

## 一、GitHub 推送（推荐）

### 1. 建空仓库

浏览器打开 <https://github.com/new>：

| 项 | 填法 | 说明 |
|---|---|---|
| Repository name | `user_growth` | 与 App 包名一致，`bench get-app` 会用到 |
| Description | `Frappe v15 用户服务开通/中止单据 + 用户增长报表 + 数据大屏（面试 Demo）` | |
| Public / Private | **Public** | 面试官要能直接打开链接 |
| Initialize this repository | **三样都不勾**（README / .gitignore / LICENSE） | 勾了会产生冲突，首次 push 会被拒 |

### 2. 加远程并推送

```bash
cd /workspace/user_growth

git remote add origin https://github.com/<你的用户名>/user_growth.git
git push -u origin main
```

### 3. 认证方式（关键，二选一）

| 方式 | 做法 | 建议 |
|---|---|---|
| **A. Personal Access Token（HTTPS）** | GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)** → Generate → 勾 `repo` → 复制 `ghp_xxx`。push 时用户名填 GitHub 用户名，**密码处粘贴 token** | 最省事。密码登录早已被 GitHub 关闭，直接输账号密码必然失败 |
| **B. SSH Key** | `ssh-keygen -t ed25519 -C "你的邮箱"` → 把 `~/.ssh/id_ed25519.pub` 内容贴到 GitHub → Settings → SSH keys → 远程地址改用 `git@github.com:<用户>/user_growth.git` | 长期使用更舒服，免重复输 token |

避免每次输 token：

```bash
git config --global credential.helper store   # 明文存在 ~/.git-credentials，个人机器可用
```

### 4. 认证成功后补两件事

**① README 里的安装地址仍是占位符**，替换成你的真实地址（`README.md` 第 37 行附近）：

```bash
sed -i 's#<your-name>#你的GitHub用户名#' README.md
git commit -am "docs: 替换 README 中的仓库地址"
git push
```

**② 打 tag**（面试官一眼看到版本号，也方便对照 CHANGELOG）：

```bash
git tag -a v1.0.0 -m "面试 Demo 交付版本"
git push origin v1.0.0
```

---

## 二、Gitee 推送（国内访问更快，可作为镜像）

1. <https://gitee.com/projects/new> 新建仓库，同样**不要**勾选初始化文件
2. 推送到 Gitee：

```bash
git remote add gitee https://gitee.com/<你的用户名>/user_growth.git
git push -u gitee main
git push gitee --tags
```

之后两端同步：

```bash
git push origin main && git push gitee main    # 或直接 git push --all
```

> **导入而非推送**也很快：Gitee 首页 → 新建仓库 → 「导入已有仓库」→ 填 GitHub 地址，自动镜像。

---

## 三、常见报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| `remote: Repository not found` | 仓库名拼错 / 私有仓库未授权 / token 无 `repo` 权限 | 核对 URL；重新生成带 `repo` 的 token |
| `Authentication failed` | 在密码框输了账号密码 | 改用 token（见 1.3） |
| `Updates were rejected... fetch first` | 建仓时勾了 README 等初始化文件 | `git pull --rebase origin main` 后再 push |
| `src refspec main does not match any` | 分支名不是 main 或还没提交 | `git branch -M main` 后重新 push |
| 推送很慢 / 超时 | 国内访问 GitHub 网络抖动 | 先推 Gitee；或配代理 `git config --global http.proxy http://127.0.0.1:端口` |
| 大文件被拒（>100MB） | 本仓库无此问题（最大 `echarts.min.js` 约 1MB） | —— |
| CI 没有触发 | 工作流只在 `push main` / PR 触发 | 确认默认分支名为 `main` |

---

## 四、推送完成后的交付清单

面试邮件/简历里只贴一个链接即可，建议附这三项：

```
GitHub:  https://github.com/<用户名>/user_growth
Gitee:   https://gitee.com/<用户名>/user_growth   （可选镜像）
演示截图: 仓库 docs/screenshots/ 下 5 张（大屏 / 单据列表 / 单据表单 / 报表 / 数据）
```

推荐给面试官的阅读顺序（**看完这四步就懂全部设计**）：

1. `docs/01-需求分析说明.md` —— 需求如何拆、口径如何定义、为什么这么设计
2. `README.md` —— 安装运行、目录结构、接口说明
3. `user_growth/user_growth/utils/analytics.py` —— **全 App 唯一聚合出口**，报表和大屏共用，口径不会两套
4. `docs/screenshots/` —— 实机运行效果

---

## 五、附录：从零把本地目录变成可推送仓库

（当前仓库已完成此步，仅供他人复现参考）

```bash
cd /workspace/user_growth
git init -b main
git add .
git commit -m "feat: 用户增长运营 App —— DocType + 报表 + 数据大屏（Frappe v15）"
git remote add origin https://github.com/<用户名>/user_growth.git
git push -u origin main
```
