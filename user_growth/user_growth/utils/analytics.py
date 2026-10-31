"""用户增长聚合层 —— 全 App 唯一的指标出口。

设计要点（面试可讲）：
1. 报表与大屏**共用本模块**，不各自写 SQL，从代码结构上保证口径一致；
2. 所有聚合下推到数据库（一次投影 + 内存滚动），不在 Python 里对每张单据查库；
3. 指标计算统一处理「期初 / 期末 / 分母为 0」等边界，前端不会出现 NaN / Infinity；
4. 客户口径与资产口径（电池块数）分离，避免「1 个客户租 20 块电池」被算成 20 个客户。
"""

import frappe
from frappe.utils import add_months, flt, get_first_day, getdate, now_datetime, nowdate

OPEN = "服务开通"
CHURN = "服务中止"
DOCTYPE = "User Service Record"

# 报表与大屏都允许的过滤器键（白名单，拼 SQL 前做校验）
FILTER_KEYS = (
	"region",
	"city",
	"battery_model",
	"customer_type",
	"lease_term",
	"source_channel",
	"churn_reason",
)


# ----------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------
def month_start(date=None):
	return getdate(get_first_day(date or nowdate()))


def build_month_series(months=12, end_date=None):
	"""生成最近 N 个月的月份键列表，格式 YYYY-MM，按时间升序。"""
	end = month_start(end_date)
	return [add_months(end, -i).strftime("%Y-%m") for i in range(months - 1, -1, -1)]


def normalize_filters(filters=None):
	"""只保留合法过滤器键，空值视为不筛选。"""
	filters = filters or {}
	return {k: v for k, v in filters.items() if k in FILTER_KEYS and v not in (None, "", [])}


def _where_sql(filters):
	"""把过滤器拼成 SQL 片段（字段名来自白名单，值走参数化，避免注入）。"""
	conds = ["docstatus = 1"]
	values = []
	for key, value in filters.items():
		conds.append(f"`{key}` = %s")
		values.append(value)
	return " AND ".join(conds), values


def _fetch_events(filters):
	"""取出全部有效单据的轻量投影，供月度滚动与结构分析使用。

	Demo 数据量在 2,000 行级别，一次投影比多次 SQL 往返更快；
	生产环境建议改为按月 GROUP BY 的 SQL 聚合（见 README「后续演进」）。
	"""
	where, values = _where_sql(filters)
	return frappe.db.sql(
		f"""SELECT record_type, open_date, churn_date, customer_code,
			monthly_fee, lost_mrr, battery_count, battery_returned,
			region, city, battery_model, customer_type, lease_term,
			source_channel, churn_reason, churn_type, customer_name
		FROM `tabUser Service Record`
		WHERE {where}""",
		values,
		as_dict=True,
	)


def _month_key(date_value):
	return getdate(date_value).strftime("%Y-%m") if date_value else None


# ----------------------------------------------------------------------
# 核心：增长 / 中止 / 在租
# ----------------------------------------------------------------------
def get_growth_summary(filters=None, months=12, end_date=None):
	"""按月返回新增 / 中止 / 净增长 / 期末在租 / 中止率 / 金额等指标。

	口径（与需求分析说明 5.3 一致）：
	- 在租客户：以 customer_code 去重，某月前开通且未中止
	- 中止率 = 当月中止数 ÷ 期初在租（期初为 0 时返回 None，前端显示 "—"）
	"""
	filters = normalize_filters(filters)
	rows = _fetch_events(filters)
	keys = build_month_series(months, end_date)
	first_key = keys[0]

	active = set()
	opening_battery = 0
	opening_fee = 0.0
	for row in rows:
		open_key = _month_key(row.open_date)
		churn_key = _month_key(row.churn_date)
		if open_key and open_key < first_key and (not churn_key or churn_key >= first_key):
			active.add(row.customer_code)
			opening_battery += int(row.battery_count or 0)
			opening_fee += flt(row.monthly_fee) * int(row.battery_count or 1)

	opens_by_month, churns_by_month = {}, {}
	for row in rows:
		if row.record_type == OPEN and row.open_date:
			opens_by_month.setdefault(_month_key(row.open_date), []).append(row)
		elif row.record_type == CHURN and row.churn_date:
			churns_by_month.setdefault(_month_key(row.churn_date), []).append(row)

	result = []
	for key in keys:
		opening = len(active)
		opening_bat = opening_battery
		opening_fee_val = opening_fee

		month_opens = opens_by_month.get(key, [])
		month_churns = churns_by_month.get(key, [])

		active |= {r.customer_code for r in month_opens}
		active -= {r.customer_code for r in month_churns}

		new_battery = sum(int(r.battery_count or 0) for r in month_opens)
		lost_battery = sum(int(r.battery_count or 0) for r in month_churns)
		new_fee = sum(flt(r.monthly_fee) * int(r.battery_count or 1) for r in month_opens)
		lost_fee = sum(flt(r.lost_mrr) for r in month_churns)

		opening_battery += new_battery - lost_battery
		opening_fee += new_fee - lost_fee

		result.append(
			{
				"month": key,
				"opening": opening,
				"new": len(month_opens),
				"churn": len(month_churns),
				"net": len(month_opens) - len(month_churns),
				"closing": len(active),
				"churn_rate": (len(month_churns) / opening * 100) if opening else None,
				"opening_battery": opening_bat,
				"new_battery": new_battery,
				"lost_battery": lost_battery,
				"closing_battery": opening_bat + new_battery - lost_battery,
				"opening_fee": opening_fee_val,
				"new_fee": new_fee,
				"lost_fee": lost_fee,
				"closing_fee": opening_fee_val + new_fee - lost_fee,
			}
		)

	return result


def get_totals(summary):
	"""把月度序列汇总成期间指标（报表汇总行 / 大屏补充信息使用）。"""
	if not summary:
		return {
			"opening": 0,
			"new": 0,
			"churn": 0,
			"net": 0,
			"closing": 0,
			"churn_rate": None,
			"net_rate": None,
			"new_fee": 0,
			"lost_fee": 0,
			"net_fee": 0,
			"new_battery": 0,
			"lost_battery": 0,
			"closing_battery": 0,
		}

	opening = summary[0]["opening"]
	new = sum(r["new"] for r in summary)
	churn = sum(r["churn"] for r in summary)
	lost = sum(r["lost_fee"] for r in summary)
	gained = sum(r["new_fee"] for r in summary)
	return {
		"opening": opening,
		"new": new,
		"churn": churn,
		"net": new - churn,
		"closing": summary[-1]["closing"],
		"churn_rate": (churn / opening * 100) if opening else None,
		"net_rate": ((new - churn) / opening * 100) if opening else None,
		"new_fee": gained,
		"lost_fee": lost,
		"net_fee": gained - lost,
		"new_battery": sum(r["new_battery"] for r in summary),
		"lost_battery": sum(r["lost_battery"] for r in summary),
		"closing_battery": summary[-1]["closing_battery"],
	}


# ----------------------------------------------------------------------
# 结构分析：原因 / 型号 / 城市 / 渠道 / 客户类型
# ----------------------------------------------------------------------
BREAKDOWN_FIELDS = (
	"churn_reason",
	"churn_type",
	"battery_model",
	"city",
	"region",
	"source_channel",
	"customer_type",
	"lease_term",
)


def get_breakdown(field, filters=None, months=12, end_date=None, record_type=None):
	"""按指定维度分组计数（用于饼图、玫瑰图、排行榜）。"""
	assert field in BREAKDOWN_FIELDS, f"unsupported breakdown field: {field}"

	filters = normalize_filters(filters)
	rows = _fetch_events(filters)
	keys = build_month_series(months, end_date)
	start, end = keys[0], keys[-1]

	counter = {}
	for row in rows:
		if record_type and row.record_type != record_type:
			continue
		date_value = row.churn_date if row.record_type == CHURN else row.open_date
		key = _month_key(date_value)
		if not key or not (start <= key <= end):
			continue
		label = row.get(field) or "未填写"
		counter[label] = counter.get(label, 0) + 1

	return sorted(
		[{"label": k, "value": v} for k, v in counter.items()],
		key=lambda x: x["value"],
		reverse=True,
	)


def get_battery_mix(filters=None, months=12, end_date=None):
	"""电池型号结构：按「期末仍在租」的客户统计电池块数，是资产视角而非客户视角。

	口径说明：一个客户若在期间内多次开通（扩容 / 换型号），以最后一次开通的型号为准，
	符合「客户当前正在用哪种电池」的业务直觉。
	"""
	filters = normalize_filters(filters)
	rows = _fetch_events(filters)
	end = build_month_series(months, end_date)[-1]

	customer_state = {}
	for row in sorted(
		[r for r in rows if r.record_type == OPEN and r.open_date],
		key=lambda r: getdate(r.open_date),
	):
		if _month_key(row.open_date) > end:
			continue
		churn_key = _month_key(row.churn_date)
		if churn_key and churn_key <= end:
			customer_state.pop(row.customer_code, None)
			continue
		customer_state[row.customer_code] = row

	counter = {}
	for row in customer_state.values():
		model = row.battery_model or "未填写"
		counter[model] = counter.get(model, 0) + int(row.battery_count or 1)

	return sorted([{"label": k, "value": v} for k, v in counter.items()], key=lambda x: x["label"])


def get_unreturned_battery(filters=None):
	"""中止但电池未归还的电池块数 —— 资产管理红线。"""
	filters = normalize_filters(filters)
	where, values = _where_sql(filters)
	value = frappe.db.sql(
		f"""SELECT COALESCE(SUM(battery_count), 0)
		FROM `tabUser Service Record`
		WHERE {where} AND record_type = %s AND IFNULL(battery_returned, 0) = 0""",
		[*values, CHURN],
	)
	return int(value[0][0]) if value else 0


def get_recent_events(limit=10, filters=None):
	"""最新开通 / 中止动态（客户名脱敏，用于大屏滚动列表）。"""
	filters = normalize_filters(filters)
	where, values = _where_sql(filters)
	columns = """record_type, customer_name, city, battery_model, monthly_fee,
		battery_count, open_date, churn_date, churn_reason"""

	opens = frappe.db.sql(
		f"""SELECT {columns} FROM `tabUser Service Record`
		WHERE {where} AND record_type = %s
		ORDER BY open_date DESC, modified DESC LIMIT %s""",
		[*values, OPEN, limit],
		as_dict=True,
	)
	churns = frappe.db.sql(
		f"""SELECT {columns} FROM `tabUser Service Record`
		WHERE {where} AND record_type = %s
		ORDER BY churn_date DESC, modified DESC LIMIT %s""",
		[*values, CHURN, limit],
		as_dict=True,
	)

	events = []
	for row in opens:
		events.append(
			{
				"type": "开通",
				"tag": "new",
				"customer": mask_name(row.customer_name),
				"city": row.city,
				"battery_model": row.battery_model,
				"text": f"{mask_name(row.customer_name)} · {row.city} · {row.battery_model} × {int(row.battery_count or 1)}",
				"date": str(row.open_date or ""),
			}
		)
	for row in churns:
		events.append(
			{
				"type": "中止",
				"tag": "churn",
				"customer": mask_name(row.customer_name),
				"city": row.city,
				"battery_model": row.battery_model,
				"text": f"{mask_name(row.customer_name)} · {row.city} · {row.churn_reason or '未填写'}",
				"date": str(row.churn_date or ""),
			}
		)

	events.sort(key=lambda x: x["date"], reverse=True)
	return events[:limit]


def mask_name(name):
	"""客户名脱敏（BC-1）：保留前 2 个字符，其余用 × 替代。"""
	if not name:
		return "—"
	name = str(name)
	if len(name) <= 3:
		return name[0] + "×"
	return name[:2] + "×" * min(len(name) - 2, 4)


# ----------------------------------------------------------------------
# 大屏快照：一次请求返回全部区块，保证同一帧数据一致
# ----------------------------------------------------------------------
@frappe.whitelist()
def get_dashboard_snapshot(months=12, region=None):
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw("请先登录", frappe.PermissionError)

	months = int(months or 12)
	filters = {"region": region} if region else {}

	summary = get_growth_summary(filters, months=months)
	totals = get_totals(summary)
	last = summary[-1] if summary else None

	return {
		"generated_at": now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
		"months": months,
		"kpi": {
			"active_customers": last["closing"] if last else 0,
			"active_battery": last["closing_battery"] if last else 0,
			"new_month": last["new"] if last else 0,
			"churn_month": last["churn"] if last else 0,
			"net_month": last["net"] if last else 0,
			"churn_rate": last["churn_rate"] if last else None,
			"monthly_fee": last["closing_fee"] if last else 0,
			"period_new": totals["new"],
			"period_churn": totals["churn"],
			"period_net": totals["net"],
			"unreturned_battery": get_unreturned_battery(filters),
		},
		"trend": summary,
		"reason_breakdown": get_breakdown("churn_reason", filters, months, record_type=CHURN)[:8],
		"city_rank": get_breakdown("city", filters, months, record_type=OPEN)[:8],
		"battery_mix": get_battery_mix(filters, months),
		"channel_rank": get_breakdown("source_channel", filters, months, record_type=OPEN)[:6],
		"customer_type_rank": get_breakdown("customer_type", filters, months, record_type=OPEN)[:6],
		"recent_events": get_recent_events(10, filters),
	}
