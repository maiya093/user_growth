// Copyright (c) 2026, Interview Demo and contributors
// For license information, please see license.txt
//
// 这里只存放「表单交互层」的默认值与提示，真正的校验与计算一律在服务端
// user_service_record.py 中完成，避免前后端两套逻辑漂移。

// 各电池型号的月租参考价（元/块/月），仅用于录入时带出，可手工修改
const BATTERY_REFERENCE_PRICE = {
	4830: 199,
	6030: 299,
	6045: 399,
};

frappe.ui.form.on("User Service Record", {
	setup(frm) {
		frm.set_query("owner_sales", () => ({
			filters: { enabled: 1 },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.dashboard.set_headline(
				__("单据已生效，客户与金额字段已锁定。如需修改，请先「取消提交」。")
			);
		}
		frm.trigger("render_hints");
	},

	record_type(frm) {
		// 编号规则与单据类型保持一致
		frm.doc.naming_series =
			frm.doc.record_type === "服务中止" ? "USR-CHRN-.YYYY.-" : "USR-OPEN-.YYYY.-";
		frm.refresh_field("naming_series");
		frm.trigger("render_hints");
	},

	battery_model(frm) {
		// IR-4：新建单据时按型号带出参考价；不覆盖用户已填写的金额
		if (frm.is_new() && !frm.doc.monthly_fee) {
			const price = BATTERY_REFERENCE_PRICE[frm.doc.battery_model];
			if (price) {
				frm.set_value("monthly_fee", price);
			}
		}
	},

	open_date(frm) {
		frm.trigger("preview_lifecycle");
	},

	churn_date(frm) {
		frm.trigger("preview_lifecycle");
	},

	preview_lifecycle(frm) {
		// IR-2：前端实时预览在租天数，保存时以服务端计算结果为准
		if (!frm.doc.open_date || !frm.doc.churn_date) {
			return;
		}
		frappe
			.xcall(
				"user_growth.user_growth.doctype.user_service_record.user_service_record.preview_lifecycle_days",
				{
					open_date: frm.doc.open_date,
					churn_date: frm.doc.churn_date,
				}
			)
			.then((days) => {
				frm.set_intro(__("预计在租 {0} 天", [days]), "blue");
			});
	},

	churn_type(frm) {
		// IR-3：欠费停机场景，原因默认「其他」并提示补充备注
		if (frm.doc.churn_type === "欠费停机" && !frm.doc.churn_reason) {
			frm.set_value("churn_reason", "其他");
		}
	},

	battery_returned(frm) {
		frm.trigger("render_hints");
	},

	render_hints(frm) {
		// BC-6 / DLG-02：电池未归还属于资产红线，表单顶部强提示
		if (frm.doc.record_type === "服务中止" && frm.doc.battery_returned === 0) {
			frm.set_intro(
				__("电池未归还：请尽快安排回收，该单据会计入报表中的「未归还电池数」。"),
				"red"
			);
		}
	},
});
