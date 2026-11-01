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
		// 去除「修改时间/评论/点赞」，表头与内容固定列宽左对齐，右侧改为「操作」列
		if (!document.getElementById("usr-list-style")) {
			const style = document.createElement("style");
			style.id = "usr-list-style";
			style.textContent = `
				.list-row .list-row-activity .modified,
				.list-row .list-row-activity .comment-count,
				.list-row .list-row-activity .mx-2,
				.list-row .list-row-activity .list-row-like { display: none !important; }
				.list-row-head .list-row-col,
				.list-row .list-row-col {
					text-align: left !important;
					justify-content: flex-start !important;
					overflow: hidden;
					text-overflow: ellipsis;
					white-space: nowrap;
					flex: 0 0 auto !important;
					box-sizing: border-box;
				}
				.list-row .level-left,
				.list-row-head .level-left { flex: 0 0 auto !important; min-width: 0 !important; max-width: 100% !important; }
				.list-row .level-right,
				.list-row-head .level-right { flex: 1 1 auto !important; justify-content: flex-end !important; }
				.list-row-head .level-right span,
				.list-row .list-row-activity { white-space: nowrap !important; }
			`;
			document.head.appendChild(style);
		}

		// 固定列宽：表头与数据行共用同一组数值，保证逐列对齐；右侧表头改为「操作」
		const COL_WIDTHS = [150, 55, 85, 90, 95, 75, 90, 100, 95, 150];
		let tries = 0;
		const applyLayout = () => {
			listview.$result.find(".list-row, .list-row-head").each(function () {
				$(this)
					.find(".level-left > .list-row-col, .list-header-subject > .list-row-col")
					.each(function (i) {
						if (i < COL_WIDTHS.length) {
							this.style.width = COL_WIDTHS[i] + "px";
							this.style.minWidth = COL_WIDTHS[i] + "px";
							this.style.maxWidth = COL_WIDTHS[i] + "px";
						}
					});
			});
			const $right = listview.$result.find(".list-row-head .level-right").first();
			if ($right.length && $right.text().trim() !== "操作") {
				$right
					.css({ display: "flex", alignItems: "center", justifyContent: "flex-start", width: "90px" })
					.html('<span class="text-muted">操作</span>');
			}
			tries += 1;
			if (tries < 12) setTimeout(applyLayout, 500);
		};
		applyLayout();

		listview.page.add_inner_button(__("只看未归还电池"), () => {
			listview.filter_area.clear();
			listview.filter_area.add([
				["User Service Record", "record_type", "=", "服务中止"],
				["User Service Record", "battery_returned", "=", 0],
			]);
		});
	},

	// 操作列：每行右侧提供快捷「编辑」按钮
	button: {
		show(doc) {
			return true;
		},
		get_label() {
			return "编辑";
		},
		get_description(doc) {
			return `打开 ${doc.name}`;
		},
		onclick(doc) {
			frappe.set_route("Form", doc.doctype, doc.name);
		},
	},
};
