# 用户增长运营 App（Frappe 自定义应用）

> 面试 Demo：`DocType`（服务开通 / 中止单据） → `Report`（用户增长分析） → `Page`（用户增长数据大屏），一条命令装完即可看效果。

![Frappe](https://img.shields.io/badge/Frappe-v15-0089FF)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 一、这个 App 做了什么

| 交付项 | 实现 | 关键点 |
| --- | --- | --- |
| **① 单据** | DocType `User Service Record` | 一张表承载「服务开通 / 服务中止」两类事件；服务端校验、提交后锁字段、**电池归还闭环** |
| **② 报表** | Script Report `用户增长分析` | 9 个过滤器 + 主图 + 3 张结构图 + 10 项指标卡 + 月/季双粒度 + 原生导出 |
| **③ 大屏** | Page `user-growth-dashboard` | 1920×1080 等比缩放、8 区块、60 秒自动刷新、**单接口快照**、失败保留旧数据 |

业务背景对齐 **浙江智格科技（换电 / 租电运营）**：客户 = 快递 / 外卖网点与骑手，服务 = 租电套餐，电池型号 4830 / 6030 / 6045，站点覆盖华东华南 + 东南亚。

> 需求分析、口径定义、验收标准见 [`docs/01-需求分析说明.md`](docs/01-需求分析说明.md)。

---

## 二、5 分钟跑起来

### 前置条件

- Frappe Framework **v15**（MariaDB 10.6+ / Redis / Node 18+）
- 已可用的 bench 环境

### 安装

```bash
cd ~/frappe-bench

# 1. 拉取 App
bench get-app https://github.com/<your-name>/user_growth.git

# 2. 安装到站点（安装完成会自动生成 24 个月演示数据）
bench --site your-site.local install-app user_growth

# 3. 启动
bench start
```

登录后用搜索框搜 **用户增长**，即可看到工作区。

### 演示数据命令

```bash
# 幂等：已有数据会跳过
bench --site your-site.local execute user_growth.setup.demo_data.run

# 重建（先清空）
bench --site your-site.local execute user_growth.setup.demo_data.clear
bench --site your-site.local execute user_growth.setup.demo_data.run

# 自定义规模
bench --site your-site.local execute user_growth.setup.demo_data.run \
  --kwargs '{"months": 12, "seed": 42, "clear": true}'
```

### 访问入口

| 功能 | 路径 |
| --- | --- |
| 工作区 | `/app/user-growth` |
| 单据列表 | `/app/user-service-record` |
| 报表 | `/app/query-report/User Growth Analysis` |
| 大屏 | `/app/user-growth-dashboard`（点右上「全屏」或按 F11） |

---

## 三、目录结构

```
user_growth/
├── user_growth/
│   ├── user_growth/
│   │   ├── doctype/user_service_record/     # ① 单据
│   │   │   ├── user_service_record.json     #   字段与权限
│   │   │   ├── user_service_record.py       #   校验、派生字段、锁字段
│   │   │   ├── user_service_record.js       #   参考价、在租天数预览、未归还提示
│   │   │   └── user_service_record_list.js  #   列表状态色 + 未归还筛选
│   │   ├── report/user_growth_report/       # ② 报表
│   │   │   ├── user_growth_report.py        #   列 / 数据 / 指标卡 / 图表
│   │   │   └── user_growth_report.js        #   过滤器 + 3 张附加结构图
│   │   ├── page/user_growth_dashboard/      # ③ 大屏（Page 定义）
│   │   ├── workspace/user_growth/           # 工作区入口
│   │   └── utils/analytics.py               # ★ 全 App 唯一聚合出口
│   ├── setup/demo_data.py                   # ★ 演示数据生成（固定种子 + 幂等）
│   ├── setup/install.py                     # 安装钩子
│   ├── public/js/user_growth_dashboard.js   # 大屏逻辑（ECharts + 刷新 + 缩放）
│   ├── public/css/user_growth_dashboard.css # 大屏样式（深色科技风）
│   ├── tests/test_analytics.py              # 口径单元测试
│   └── hooks.py
├── docs/01-需求分析说明.md
├── pyproject.toml
└── README.md
```

---

## 四、技术决策（面试常问的 5 个「为什么」）

### 1. 为什么开通用一张表而不是两张？

开通与中止字段重合度约 80%（客户、型号、金额、渠道）。拆两张表意味着报表两次 JOIN、Mock 与校验代码翻倍。用 `record_type` 区分后，**一次聚合同时拿到「进」与「出」**，中止单还能自然带出原开通信息。
> 生产版演进：`Customer` / `Station` / `Battery` 独立主数据 + 变更单（生命周期链）。

### 2. 为什么报表和大屏共用 `utils/analytics.py`？

**一致性靠代码结构保证，而不是靠人自觉。** 如果报表一套 SQL、大屏再写一套，半年后必然出现"大屏 1,204 家、报表 1,198 家"的经典事故。本 App 所有指标只有一个函数出口，口径调整只改一处，并可被单元测试覆盖。

### 3. 为什么大屏只发一个接口请求？

8 个区块各发一个请求，会出现"趋势图已更新、环形图还是上一分钟"的割裂感。`get_dashboard_snapshot()` 返回一个**数据快照**，从架构上保证同一帧内所有区块属于同一时刻。

### 4. 为什么用 `transform: scale()` 而不是响应式布局？

大屏不是普通网页。LED / 拼接屏分辨率五花八门（1920×1080、2560×1440、3840×2160），**等比缩放保证任何分辨率下都不错位、无滚动条**；响应式栅格反而会在某些宽度把卡片挤变形。基准稿 1920×1080，JS 按容器尺寸计算 scale。

### 5. 为什么状态字段从 `docstatus` 派生？

Frappe 的 `docstatus`（0 草稿 / 1 已生效 / 2 已取消）本身就是状态机。再存一个 `status` 库字段，一定会出现"status 已生效但 docstatus 还是 0"的脏数据。所以 `status` 在 `validate` 中由 `docstatus` 回写，只读展示。

---

## 五、指标口径（口径唯一是这份 Demo 最在意的点）

| 指标 | 公式 | 备注 |
| --- | --- | --- |
| 在租客户 | `customer_code` 去重，期内开通 − 期内中止 | 客户数不按电池数计 |
| 新增 / 中止 | 按 `open_date` / `churn_date` 落入月份 | 仅 `docstatus = 1` |
| 净增长 | 新增 − 中止 | 可为负 |
| 期初 / 期末在租 | 期末 = 期初 + 新增 − 中止 | **恒等式有单元测试守护** |
| **中止率** | `当月中止 ÷ 期初在租` | 期初为 0 返回 `None`，前端显示 `—` |
| 新增 / 中止月租 | `monthly_fee × battery_count` 累加 | 单位 CNY/月 |
| 在租电池 | 期末在租客户的 `battery_count` 累加 | 资产口径，与客户口径分离 |
| 未归还电池 | `SUM(battery_count) WHERE 中止 AND battery_returned = 0` | 资产管理红线 |

> 中止率分母有期初 / 平均 / 期末三种主流口径。本 Demo 选**期初**：分母稳定、月度可比。取舍理由写在需求文档 5.3，也是面试可展开讨论的点。

---

## 六、数据结构速览

| 分组 | 字段 |
| --- | --- |
| 客户 | 客户名称、客户编号、客户类型（快递网点/外卖站点/同城配送/企业车队/个人骑手）、大区、城市、换电柜站点 |
| 租电 | 电池型号（4830/6030/6045）、租电电池数、租期（月/季/年）、月租金额、合同期租金总额、获客渠道、负责人 |
| 中止 | 中止日期、中止类型、中止原因、**电池已归还入柜**、在租天数、中止月租损失 |
| 状态 | 状态（由 docstatus 派生，只读） |

演示数据形态（seed = `20261029`，24 个月）：开通约 1,500 条、中止约 300~500 条；电池型号分布 6030 ≈ 45%、4830 ≈ 35%、6045 ≈ 20%；城市集中在杭州 / 上海 / 广州 / 深圳，海外（曼谷 / 吉隆坡）约 5%；中止原因 TOP 为单价过高 → 站点太远 → 车辆淘汰；约 3% 中止单电池未归还。

---

## 七、验收自查（对应需求文档 AC）

| # | 检查项 | 怎么验 |
| --- | --- | --- |
| AC-1 | 安装即可用 | 干净站点 `install-app`，工作区出现、数据已生成 |
| AC-3 | 中止单必填校验 | 选「服务中止」不填原因直接保存 → 报错 |
| AC-4 | 日期倒挂 | 中止日期早于开通日期 → 报错 |
| AC-5 | 在租天数 | 开通 2025-01-10、中止 2025-07-10 → 181 |
| AC-6 | 提交后锁字段 | 已提交单据改月租 → 被拦截 |
| AC-7 | 造数幂等 | 再跑一次 `demo_data.run` → 总数不变 |
| AC-8 | 指标恒等式 | 报表任意月份：期末 = 期初 + 新增 − 中止 |
| AC-10 | 空态 | 过滤器选到无数据条件 → 空态，无 NaN |
| AC-12 | 大屏 8 区块 | 打开 `/app/user-growth-dashboard` |
| AC-13 | 自动刷新 | 等 60 秒，更新时间变化且**无白屏** |
| AC-16 | 电池未归还 | 中止单取消勾选归还 → 列表标红、报表「未归还电池数」+N |

单元测试：

```bash
bench --site your-site.local run-tests --app user_growth
```

---

## 八、演示数据说明

⚠️ 所有客户名称、金额、站点均为**程序生成的虚构数据**，仅用于功能演示，请勿用于生产环境或对外宣称业务数据。

---

## 九、验收记录（本地实机验证）

在 Frappe **v15.124.0** + MariaDB 10.6 + Redis 环境实机安装并验证：

```
install-app user_growth          → 成功，自动生成演示数据
演示数据                          → 开通 1,551 条 / 中止 514 条 / 未归还电池 19 单（seed=20261029）
报表 User Growth Analysis         → 12 行 × 13 列 + 10 张指标卡 + 主图，耗时 0.30s
指标恒等式（期末=期初+新增−中止）  → 0 处违例
大屏快照接口                      → 10 个区块数据，耗时 0.16s
单元测试                          → 8 passed
```

## 十、License

MIT
