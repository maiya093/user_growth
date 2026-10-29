# Copyright (c) 2026, Interview Demo and contributors
# For license information, please see license.txt

"""演示数据生成器。

设计目标（对应需求分析说明 FR-1.13 ~ FR-1.17）：
1. 覆盖最近 24 个自然月；
2. 数据形态可信：基线 + 增长趋势 + 季节波动（Q4 骑手旺季）+ 噪声；
3. 固定随机种子，任何人安装后数据形态一致；
4. 幂等：已有数据则跳过，避免重复插入。
"""

import random

import frappe
from frappe.utils import add_days, add_months, get_first_day, get_last_day, getdate, nowdate

SEED = 20261029
MONTHS = 24

# 城市与大区映射：贴合公司在华东华南的布局 + 东南亚海外市场
CITY_REGION = {
	"杭州": "华东",
	"上海": "华东",
	"南京": "华东",
	"苏州": "华东",
	"宁波": "华东",
	"广州": "华南",
	"深圳": "华南",
	"东莞": "华南",
	"佛山": "华南",
	"曼谷": "海外",
	"吉隆坡": "海外",
}
CITY_WEIGHT = {
	"杭州": 18,
	"上海": 15,
	"广州": 13,
	"深圳": 12,
	"苏州": 9,
	"南京": 8,
	"东莞": 8,
	"佛山": 6,
	"宁波": 5,
	"曼谷": 3,
	"吉隆坡": 3,
}

BATTERY_MODEL = [("6030", 45), ("4830", 35), ("6045", 20)]
CUSTOMER_TYPE = [("快递网点", 35), ("外卖站点", 30), ("同城配送", 20), ("企业车队", 10), ("个人骑手", 5)]
LEASE_TERM = [("月租", 55), ("季租", 30), ("年租", 15)]
CHANNEL = [("网点直签", 30), ("渠道代理", 25), ("地推活动", 20), ("老客推荐", 15), ("平台合作", 10)]

# 中止原因权重：价格与站点距离是换电业务最大的两个痛点
CHURN_REASON = [
	("单价过高", 22),
	("站点太远", 18),
	("车辆淘汰", 14),
	("续航不足", 12),
	("竞品更低", 10),
	("电池老旧", 9),
	("押金与结算纠纷", 7),
	("客户停业", 5),
	("其他", 3),
]
CHURN_TYPE = [("主动退租", 55), ("到期未续", 20), ("欠费停机", 15), ("站点合并", 6), ("客户停业", 4)]

# 各型号月租参考价（元/块/月）
MODEL_PRICE = {"4830": 199, "6030": 299, "6045": 399}

BRAND = ["顺", "圆", "中", "京", "申", "极", "达", "闪", "蜂", "优", "快", "速", "联", "众", "新"]
SUFFIX = ["快递", "速运", "物流", "配送", "供应链", "驿站"]
STATION = ["万达", "银泰", "科技园", "物流园", "北站", "城南", "工业区"]


def _weighted_choice(pairs):
	values = [p[0] for p in pairs]
	weights = [p[1] for p in pairs]
	return random.choices(values, weights=weights, k=1)[0]


def _rand_date_in_month(month_start, not_after=None):
	last = get_last_day(month_start)
	if not_after and getdate(not_after) < getdate(last):
		last = not_after
	span = (getdate(last) - getdate(month_start)).days
	return add_days(month_start, random.randint(0, max(span, 0)))


def run(months=MONTHS, seed=SEED, clear=False, silent=False, **kwargs):
	"""生成演示数据。

	用法：
	    bench --site <site> execute user_growth.setup.demo_data.run
	    bench --site <site> execute user_growth.setup.demo_data.run --kwargs '{"months": 12, "clear": true}'
	"""
	random.seed(seed)

	if clear:
		frappe.db.delete("User Service Record")
		frappe.db.commit()

	existing = frappe.db.count("User Service Record")
	if existing:
		message = "已有演示数据，跳过生成（如需重建请先执行 user_growth.setup.demo_data.clear）"
		if not silent:
			print(message)
		return {"skipped": True, "existing": existing}

	today = getdate(nowdate())
	end_month = get_first_day(today)
	month_starts = [add_months(end_month, -(months - 1 - i)) for i in range(months)]

	total_open = 0
	total_churn = 0
	active_pool = []

	for idx, month_start in enumerate(month_starts):
		# 基线 + 线性增长 + 季节性（Q4 与春季骑手旺季）+ 噪声
		base = 42 + idx * 1.6
		month_no = getdate(month_start).month
		season = 1.25 if month_no in (10, 11, 12) else (1.1 if month_no in (3, 4) else 1.0)
		new_count = max(int(base * season * random.uniform(0.85, 1.15)), 15)

		for _ in range(new_count):
			open_date = _rand_date_in_month(month_start, not_after=today)
			city = _weighted_choice(list(CITY_WEIGHT.items()))
			model = _weighted_choice(BATTERY_MODEL)
			doc = frappe.get_doc(
				{
					"doctype": "User Service Record",
					"record_type": "服务开通",
					"naming_series": "USR-OPEN-.YYYY.-",
					"customer_name": f"{city}{random.choice(BRAND)}{random.choice(SUFFIX)}{random.randint(1, 99):02d}号",
					"customer_code": f"C{frappe.generate_hash(length=8).upper()}",
					"customer_type": _weighted_choice(CUSTOMER_TYPE),
					"region": CITY_REGION[city],
					"city": city,
					"station": f"{city}·{random.choice(STATION)}柜",
					"battery_model": model,
					"battery_count": random.choices([1, 2, 3, 5, 8], weights=[45, 28, 15, 8, 4], k=1)[0],
					"lease_term": _weighted_choice(LEASE_TERM),
					"monthly_fee": MODEL_PRICE[model] + random.choice([0, 0, 0, 20, -20]),
					"source_channel": _weighted_choice(CHANNEL),
					"open_date": open_date,
				}
			)
			doc.insert(ignore_permissions=True)
			doc.submit()
			total_open += 1
			active_pool.append(doc)

		# 中止：从存量池按 3%~9% 抽取；当月新增不立刻流失，避免「当月开、当月关」的假数据
		candidates = [d for d in active_pool if getdate(d.open_date) < getdate(month_start)]
		churn_count = min(
			int(len(candidates) * random.uniform(0.03, 0.09)),
			max(int(new_count * 0.45), 3),
		)
		random.shuffle(candidates)
		for doc in candidates[:churn_count]:
			churn_date = _rand_date_in_month(month_start, not_after=today)
			if getdate(churn_date) < getdate(doc.open_date):
				churn_date = doc.open_date
			churn_doc = frappe.get_doc(
				{
					"doctype": "User Service Record",
					"record_type": "服务中止",
					"naming_series": "USR-CHRN-.YYYY.-",
					"customer_name": doc.customer_name,
					# 中止单沿用客户编号（同一客户的开通/中止记录共享 customer_code），
					# 因此 customer_code 不设唯一约束，去重逻辑在 analytics 层完成。
					"customer_code": doc.customer_code,
					"customer_type": doc.customer_type,
					"region": doc.region,
					"city": doc.city,
					"station": doc.station,
					"battery_model": doc.battery_model,
					"battery_count": doc.battery_count,
					"lease_term": doc.lease_term,
					"monthly_fee": doc.monthly_fee,
					"source_channel": doc.source_channel,
					"open_date": doc.open_date,
					"churn_date": churn_date,
					"churn_type": _weighted_choice(CHURN_TYPE),
					"churn_reason": _weighted_choice(CHURN_REASON),
					# 约 3% 的中止单电池未归还，用于验证资产异常分支
					"battery_returned": 0 if random.random() < 0.03 else 1,
				}
			)
			churn_doc.insert(ignore_permissions=True)
			churn_doc.submit()
			total_churn += 1
			active_pool.remove(doc)

	frappe.db.commit()
	result = {"created_open": total_open, "created_churn": total_churn, "months": months, "seed": seed}
	if not silent:
		print(f"演示数据生成完成：开通 {total_open} 条，中止 {total_churn} 条（近 {months} 个月，seed={seed}）")
	return result


def clear():
	"""清空演示数据（重建前调用）。"""
	frappe.db.delete("User Service Record")
	frappe.db.commit()
	print("已清空 User Service Record")
	return {"cleared": True}
