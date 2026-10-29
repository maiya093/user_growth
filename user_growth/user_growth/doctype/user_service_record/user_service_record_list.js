// Copyright (c) 2026, Interview Demo and contributors
// For license information, please see license.txt
//
// 列表视图增强：
// 1) 中止但电池未归还的单据标红，资产管理一眼可见；
// 2) 提供「只看未归还电池」快捷筛选。

frappe.listview_settings["User Service Record"] = {
	add_fields: ["record_type", "battery_returned", "status", "city"],

	get_indicator(doc) {
		if (doc.docstatus === 0) {
			return [__("草稿"), "orange", "docstatus,=,0"];
		}
		if (doc.docstatus === 2) {
			return [__("已取消"), "grey", "docstatus,=,2"];
		}
		if (doc.record_type === "服务中止" && !doc.battery_returned) {
			return [__("电池未归还"), "red", "record_type,=,服务中止"];
		}
		if (doc.record_type === "服务中止") {
			return [__("已中止"), "grey", "record_type,=,服务中止"];
		}
		return [__("在租"), "green", "record_type,=,服务开通"];
	},

	onload(listview) {
		listview.page.add_inner_button(__("只看未归还电池"), () => {
			listview.filter_area.clear();
			listview.filter_area.add([
				["User Service Record", "record_type", "=", "服务中止"],
				["User Service Record", "battery_returned", "=", 0],
			]);
		});
	},
};
