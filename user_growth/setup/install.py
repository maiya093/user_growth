# Copyright (c) 2026, Interview Demo and contributors
# For license information, please see license.txt

import frappe


def after_install():
	"""安装完成后自动生成演示数据，让评审方 install-app 后即可看到效果。"""
	create_roles()
	ensure_demo_data()


def ensure_demo_data():
	"""迁移时兜底：仅在没有任何单据时生成，脚本本身也带幂等保护。"""
	from user_growth.setup.demo_data import run

	if not frappe.db.count("User Service Record"):
		run(months=24, seed=20261029, silent=True)


def create_roles():
	for role in ("Growth Operator", "Growth Manager"):
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role,
					"desk_access": 1,
				}
			).insert(ignore_permissions=True)
