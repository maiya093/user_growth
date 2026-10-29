# Copyright (c) 2026, Interview Demo and contributors
"""聚合口径单元测试 —— 核心断言：期末在租 = 期初在租 + 新增 − 中止。

运行方式（在 bench 目录下）：
    bench --site <site> run-tests --app user_growth
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from user_growth.user_growth.utils import analytics


class TestAnalytics(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("User Service Record")
		frappe.db.commit()

	def _make(self, record_type, code, open_date, churn_date=None, reason="单价过高", returned=1):
		doc = frappe.get_doc(
			{
				"doctype": "User Service Record",
				"record_type": record_type,
				"customer_code": code,
				"customer_name": f"测试客户{code}",
				"customer_type": "快递网点",
				"region": "华东",
				"city": "杭州",
				"battery_model": "6030",
				"battery_count": 2,
				"lease_term": "月租",
				"monthly_fee": 299,
				"source_channel": "网点直签",
				"open_date": open_date,
				"churn_date": churn_date,
				"churn_type": "主动退租" if churn_date else None,
				"churn_reason": reason if churn_date else None,
				"battery_returned": returned,
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def test_identity_holds(self):
		"""任意月份都满足：期末 = 期初 + 新增 − 中止。"""
		self._make("服务开通", "T001", "2025-01-05")
		self._make("服务开通", "T002", "2025-02-05")
		self._make("服务中止", "T001", "2025-01-05", "2025-04-10")

		summary = analytics.get_growth_summary(months=6, end_date="2025-06-01")
		for row in summary:
			self.assertEqual(row["closing"], row["opening"] + row["new"] - row["churn"])

	def test_opening_balance(self):
		"""1 月开通、4 月中止：5 月起存量应回到 0。"""
		self._make("服务开通", "T003", "2025-01-05")
		self._make("服务中止", "T003", "2025-01-05", "2025-04-10")
		summary = {r["month"]: r for r in analytics.get_growth_summary(months=6, end_date="2025-06-01")}
		self.assertEqual(summary["2025-03"]["closing"], 1)
		self.assertEqual(summary["2025-04"]["churn"], 1)
		self.assertEqual(summary["2025-06"]["closing"], 0)

	def test_churn_rate_none_when_empty(self):
		"""期初为 0 时中止率必须为 None（前端显示 —），不能抛除零异常。"""
		self._make("服务开通", "T004", "2025-06-10")
		summary = analytics.get_growth_summary(months=3, end_date="2025-06-01")
		self.assertIsNone(summary[0]["churn_rate"])

	def test_fee_and_battery(self):
		"""金额与电池块数按 battery_count 累加，客户数按客户去重。

		注意：months=2 / end_date=2025-06-01 统计的是 5、6 两个月，
		所以这里要断言「5 月」那一行，而不是最后一行（6 月）。
		"""
		self._make("服务开通", "T005", "2025-05-10")
		summary = analytics.get_growth_summary(months=2, end_date="2025-06-01")
		may = summary[0]
		self.assertEqual(may["month"], "2025-05")
		self.assertEqual(may["new"], 1)
		self.assertEqual(may["new_battery"], 2)
		self.assertEqual(may["new_fee"], 598)

	def test_unreturned_battery(self):
		self._make("服务开通", "T006", "2025-01-05")
		self._make("服务中止", "T006", "2025-01-05", "2025-03-10", returned=0)
		self.assertEqual(analytics.get_unreturned_battery(), 2)

	def test_mask_name(self):
		self.assertEqual(analytics.mask_name("杭州顺丰快递01号")[:2], "杭州")
		self.assertIn("×", analytics.mask_name("杭州顺丰快递01号"))

	def test_doc_validation(self):
		"""中止单缺少原因应被拦截；日期倒挂应被拦截。"""
		with self.assertRaises(frappe.ValidationError):
			self._make("服务中止", "T007", "2025-01-05", "2025-02-05", reason="")

		doc = frappe.get_doc(
			{
				"doctype": "User Service Record",
				"record_type": "服务中止",
				"customer_code": "T008",
				"customer_name": "测试客户T008",
				"customer_type": "快递网点",
				"region": "华东",
				"city": "杭州",
				"battery_model": "6030",
				"battery_count": 1,
				"lease_term": "月租",
				"monthly_fee": 299,
				"open_date": "2025-05-01",
				"churn_date": "2025-04-01",
				"churn_type": "主动退租",
				"churn_reason": "单价过高",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_lifecycle_days(self):
		doc = self._make("服务开通", "T009", "2025-01-10")
		doc2 = frappe.get_doc(
			{
				"doctype": "User Service Record",
				"record_type": "服务中止",
				"customer_code": "T009",
				"customer_name": "测试客户T009",
				"customer_type": "快递网点",
				"region": "华东",
				"city": "杭州",
				"battery_model": "6030",
				"battery_count": 1,
				"lease_term": "月租",
				"monthly_fee": 299,
				"open_date": "2025-01-10",
				"churn_date": "2025-07-10",
				"churn_type": "主动退租",
				"churn_reason": "单价过高",
			}
		)
		doc2.insert(ignore_permissions=True)
		self.assertEqual(doc2.lifecycle_days, 181)
