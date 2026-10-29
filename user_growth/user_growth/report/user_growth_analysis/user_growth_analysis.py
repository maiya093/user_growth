# Copyright (c) 2026, Interview Demo and contributors
# For license information, please see license.txt

"""用户增长分析报表（Script Report）。

数据全部来自 utils/analytics.py，与数据大屏共用同一套聚合口径。
"""

import frappe
from frappe import _
from frappe.utils import fmt_money

from user_growth.user_growth.utils import analytics

CHURN = analytics.CHURN
OPEN = analytics.OPEN


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	# Frappe v15 的 6 元组顺序：columns, result, message, chart, report_summary, skip_total_row
	# message 里放口径说明，report_summary 放指标卡（前端渲染成卡片）。
	return (
		get_columns(filters),
		data,
		get_message(filters),
		get_chart(filters, data),
		get_cards(filters, data),
		False,
	)


def get_message(filters):
	months = int(filters.get("months") or 12)
	granularity = filters.get("granularity") or "月"
	return (
		f"统计范围：近 {months} 个月 · 粒度：{granularity}；"
		"中止率 = 当期中止 ÷ 期初在租；客户按客户编号去重；月租 = 单块月租 × 电池数。"
	)


# ---------------------------------------------------------------------------
# 列
# ---------------------------------------------------------------------------
def get_columns(filters):
	period_label = _("季度") if filters.get("granularity") == "季" else _("月份")
	return [
		{"fieldname": "period", "label": period_label, "fieldtype": "Data", "width": 110},
		{"fieldname": "opening", "label": _("期初在租"), "fieldtype": "Int", "width": 100},
		{"fieldname": "new", "label": _("新增客户"), "fieldtype": "Int", "width": 100},
		{"fieldname": "churn", "label": _("中止客户"), "fieldtype": "Int", "width": 100},
		{"fieldname": "net", "label": _("净增长"), "fieldtype": "Int", "width": 100},
		{"fieldname": "closing", "label": _("期末在租"), "fieldtype": "Int", "width": 100},
		{"fieldname": "churn_rate", "label": _("中止率"), "fieldtype": "Percent", "width": 100},
		{"fieldname": "new_fee", "label": _("新增月租"), "fieldtype": "Currency", "width": 120, "options": "currency"},
		{"fieldname": "lost_fee", "label": _("中止月租"), "fieldtype": "Currency", "width": 120, "options": "currency"},
		{"fieldname": "net_fee", "label": _("净月租"), "fieldtype": "Currency", "width": 120, "options": "currency"},
		{"fieldname": "new_battery", "label": _("新增电池(块)"), "fieldtype": "Int", "width": 110},
		{"fieldname": "lost_battery", "label": _("回收电池(块)"), "fieldtype": "Int", "width": 120},
		{"fieldname": "closing_battery", "label": _("在租电池(块)"), "fieldtype": "Int", "width": 120},
	]


# ---------------------------------------------------------------------------
# 数据
# ---------------------------------------------------------------------------
def build_filters(filters):
	return {
		"region": filters.get("region_select") or filters.get("region"),
		"city": filters.get("city"),
		"battery_model": filters.get("battery_model"),
		"customer_type": filters.get("customer_type"),
		"lease_term": filters.get("lease_term"),
		"source_channel": filters.get("source_channel"),
		"churn_reason": filters.get("churn_reason"),
	}


def get_data(filters):
	months = int(filters.get("months") or 12)
	summary = analytics.get_growth_summary(build_filters(filters), months=months)
	if filters.get("granularity") == "季":
		return aggregate_by_quarter(summary)

	return [
		{
			"period": item["month"],
			"opening": item["opening"],
			"new": item["new"],
			"churn": item["churn"],
			"net": item["net"],
			"closing": item["closing"],
			"churn_rate": item["churn_rate"],
			"new_fee": item["new_fee"],
			"lost_fee": item["lost_fee"],
			"net_fee": item["new_fee"] - item["lost_fee"],
			"new_battery": item["new_battery"],
			"lost_battery": item["lost_battery"],
			"closing_battery": item["closing_battery"],
		}
		for item in summary
	]


def aggregate_by_quarter(summary):
	"""季度粒度：期初取季度首月期初，期末取季度末月期末，其余累加。"""
	buckets, order = {}, []
	for item in summary:
		year, month = item["month"].split("-")
		quarter = f"{year}-Q{(int(month) - 1) // 3 + 1}"
		if quarter not in buckets:
			buckets[quarter] = {
				"period": quarter,
				"opening": item["opening"],
				"new": 0,
				"churn": 0,
				"new_fee": 0,
				"lost_fee": 0,
				"new_battery": 0,
				"lost_battery": 0,
			}
			order.append(quarter)
		bucket = buckets[quarter]
		bucket["new"] += item["new"]
		bucket["churn"] += item["churn"]
		bucket["new_fee"] += item["new_fee"]
		bucket["lost_fee"] += item["lost_fee"]
		bucket["new_battery"] += item["new_battery"]
		bucket["lost_battery"] += item["lost_battery"]
		bucket["closing"] = item["closing"]
		bucket["closing_battery"] = item["closing_battery"]

	rows = []
	for quarter in order:
		bucket = buckets[quarter]
		bucket["net"] = bucket["new"] - bucket["churn"]
		bucket["net_fee"] = bucket["new_fee"] - bucket["lost_fee"]
		bucket["churn_rate"] = (bucket["churn"] / bucket["opening"] * 100) if bucket["opening"] else None
		rows.append(bucket)
	return rows


# ---------------------------------------------------------------------------
# 指标卡
# ---------------------------------------------------------------------------
def get_cards(filters, data):
	if not data:
		return []

	opening = data[0]["opening"]
	new = sum(r["new"] for r in data)
	churn = sum(r["churn"] for r in data)
	new_fee = sum(r["new_fee"] for r in data)
	lost_fee = sum(r["lost_fee"] for r in data)
	# 期间中止率：分母用「期初在租」，与月度口径保持一致（不是简单按月相加）
	churn_rate = (churn / opening * 100) if opening else None
	unreturned = analytics.get_unreturned_battery(build_filters(filters))

	def pct(value):
		return "—" if value is None else f"{value:.2f}%"

	def money(value):
		return fmt_money(value, currency="CNY")

	return [
		{"label": _("期初在租客户"), "value": opening, "datatype": "Int", "indicator": "Blue"},
		{"label": _("期间新增"), "value": new, "datatype": "Int", "indicator": "Green"},
		{"label": _("期间中止"), "value": churn, "datatype": "Int", "indicator": "Red"},
		{
			"label": _("净增长"),
			"value": new - churn,
			"datatype": "Int",
			"indicator": "Green" if new >= churn else "Red",
		},
		{"label": _("期末在租"), "value": data[-1]["closing"], "datatype": "Int", "indicator": "Blue"},
		{"label": _("中止率（÷期初在租）"), "value": pct(churn_rate), "indicator": "Orange"},
		{"label": _("新增月租"), "value": money(new_fee), "indicator": "Green"},
		{"label": _("中止月租"), "value": money(lost_fee), "indicator": "Red"},
		{
			"label": _("净月租"),
			"value": money(new_fee - lost_fee),
			"indicator": "Green" if new_fee >= lost_fee else "Red",
		},
		{
			"label": _("未归还电池（块）"),
			"value": unreturned,
			"datatype": "Int",
			"indicator": "Red" if unreturned else "Green",
		},
	]


# ---------------------------------------------------------------------------
# 图表：主图为增长趋势，附加 3 张结构图由前端 JS 渲染
# ---------------------------------------------------------------------------
def get_chart(filters, data):
	if not data:
		return None

	months = int(filters.get("months") or 12)
	filter_dict = build_filters(filters)

	reason = analytics.get_breakdown("churn_reason", filter_dict, months, record_type=CHURN)
	battery = analytics.get_battery_mix(filter_dict, months)
	city = analytics.get_breakdown("city", filter_dict, months, record_type=OPEN)[:8]

	return {
		"data": {
			"labels": [row["period"] for row in data],
			"datasets": [
				{"name": _("新增客户"), "values": [row["new"] for row in data]},
				{"name": _("中止客户"), "values": [row["churn"] for row in data]},
				{"name": _("净增长"), "values": [row["net"] for row in data]},
			],
		},
		"type": "axis-mixed",
		"colors": ["#22D3EE", "#F87171", "#34D399"],
		"extra_charts": {
			"reason": {
				"title": _("中止原因分布"),
				"type": "donut",
				"labels": [x["label"] for x in reason],
				"values": [x["value"] for x in reason],
			},
			"battery": {
				"title": _("在租电池结构（按型号 · 块）"),
				"type": "bar",
				"labels": [x["label"] for x in battery],
				"values": [x["value"] for x in battery],
			},
			"city": {
				"title": _("城市新增 TOP 8"),
				"type": "bar-horizontal",
				"labels": [x["label"] for x in city],
				"values": [x["value"] for x in city],
			},
		},
	}
