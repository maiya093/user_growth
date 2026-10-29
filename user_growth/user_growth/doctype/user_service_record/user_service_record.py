# Copyright (c) 2026, Interview Demo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, flt, getdate

OPEN = "服务开通"
CHURN = "服务中止"

# 单据提交后不允许修改的关键字段（防止历史数据被改坏导致报表失真）
LOCKED_AFTER_SUBMIT = (
	"customer_code",
	"customer_name",
	"record_type",
	"battery_model",
	"monthly_fee",
	"open_date",
	"churn_date",
)

LEASE_TERM_MONTHS = {"月租": 1, "季租": 3, "年租": 12}


class UserServiceRecord(Document):
	def validate(self):
		self.set_status()
		self.validate_record_type()
		self.set_naming_series()
		self.compute_derived_fields()
		self.validate_dates()
		self.validate_numbers()
		self.warn_duplicate_open()
		self.validate_locked_fields()

	def before_insert(self):
		if not self.owner_sales:
			self.owner_sales = frappe.session.user

	# ------------------------------------------------------------------
	# 校验与计算
	# ------------------------------------------------------------------
	def set_status(self):
		"""状态由 docstatus 派生，避免再造一个库字段与 Frappe 状态机打架。"""
		self.status = {0: "草稿", 1: "已生效", 2: "已取消"}.get(self.docstatus or 0, "草稿")

	def validate_record_type(self):
		if self.record_type not in (OPEN, CHURN):
			frappe.throw(_("单据类型只能为「服务开通」或「服务中止」"))

	def set_naming_series(self):
		"""编号规则与单据类型保持一致。"""
		expected = "USR-CHRN-.YYYY.-" if self.record_type == CHURN else "USR-OPEN-.YYYY.-"
		if self.is_new() or not self.naming_series:
			self.naming_series = expected

	def compute_derived_fields(self):
		if not self.monthly_fee:
			self.monthly_fee = 0
		if not self.battery_count:
			self.battery_count = 1

		months = LEASE_TERM_MONTHS.get(self.lease_term, 1)
		self.total_fee = flt(self.monthly_fee) * months * self.battery_count

		if self.record_type == CHURN:
			if self.open_date and self.churn_date:
				self.lifecycle_days = max(date_diff(self.churn_date, self.open_date), 0)
			self.lost_mrr = flt(self.monthly_fee) * (self.battery_count or 1)
		else:
			# 开通单不承载中止信息，主动清空，避免脏数据进入统计
			self.churn_date = None
			self.churn_type = None
			self.churn_reason = None
			self.lifecycle_days = 0
			self.lost_mrr = 0
			self.battery_returned = 0

	def validate_dates(self):
		if not self.open_date:
			frappe.throw(_("请填写开通日期"))

		if self.record_type == CHURN:
			if not self.churn_date:
				frappe.throw(_("服务中止单必须填写「中止日期」"))
			if not self.churn_type:
				frappe.throw(_("服务中止单必须填写「中止类型」"))
			if not self.churn_reason:
				frappe.throw(_("服务中止单必须填写「中止原因」"))
			if getdate(self.churn_date) < getdate(self.open_date):
				frappe.throw(_("中止日期不得早于开通日期"))

	def validate_numbers(self):
		if flt(self.monthly_fee) < 0:
			frappe.throw(_("月租金额不得为负"))
		if (self.battery_count or 0) < 1:
			frappe.throw(_("租电电池数至少为 1"))

	def warn_duplicate_open(self):
		"""同一客户可能存在多个站点，因此只警告不阻断。"""
		if self.record_type != OPEN or not self.customer_code:
			return

		existing = frappe.db.count(
			"User Service Record",
			{
				"customer_code": self.customer_code,
				"record_type": OPEN,
				"docstatus": 1,
				"name": ["!=", self.name or ""],
			},
		)
		if existing:
			frappe.msgprint(
				_("检测到客户 {0} 已存在 {1} 条有效的开通记录，请确认是否为多站点 / 扩容场景。").format(
					frappe.bold(self.customer_code), existing
				),
				title=_("重复开通提示"),
				indicator="orange",
				alert=True,
			)

	def validate_locked_fields(self):
		if self.is_new() or self.docstatus != 1:
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changed = [f for f in LOCKED_AFTER_SUBMIT if self.get(f) != before.get(f)]
		if changed and frappe.session.user != "Administrator":
			frappe.throw(
				_("单据已提交，以下字段不可直接修改：{0}。如需调整请先取消提交。").format(", ".join(changed))
			)


@frappe.whitelist()
def preview_lifecycle_days(open_date, churn_date):
	"""表单前端实时预览在租天数，最终以服务端保存结果为准。"""
	if not open_date or not churn_date:
		return 0
	return max(date_diff(churn_date, open_date), 0)
