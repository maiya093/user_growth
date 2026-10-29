// Copyright (c) 2026, Interview Demo and contributors
// For license information, please see license.txt
//
// 报表前端扩展：
// 1) 定义过滤器（后端 execute 已对 region/region_select 做兼容）；
// 2) 主图之外追加「中止原因 / 电池型号 / 城市 TOP」三张结构图；
// 3) 顶部展示口径说明，并给净增长、中止率加颜色规则。

frappe.query_reports["用户增长分析"] = {
	filters: [
		{
			fieldname: "months",
			label: __("统计范围（近 N 个月）"),
			fieldtype: "Select",
			options: ["3", "6", "12", "24"].join("\n"),
			default: "12",
			reqd: 1,
		},
		{
			fieldname: "granularity",
			label: __("统计粒度"),
			fieldtype: "Select",
			options: ["月", "季"].join("\n"),
			default: "月",
			reqd: 1,
		},
		{
			fieldname: "region_select",
			label: __("大区"),
			fieldtype: "Select",
			options: ["", "华东", "华南", "华中", "西南", "华北", "东北", "西北", "海外"].join("\n"),
		},
		{
			fieldname: "city",
			label: __("城市"),
			fieldtype: "Select",
			options: ["", "杭州", "上海", "南京", "苏州", "宁波", "广州", "深圳", "东莞", "佛山", "曼谷", "吉隆坡"].join("\n"),
		},
		{
			fieldname: "battery_model",
			label: __("电池型号"),
			fieldtype: "Select",
			options: ["", "4830", "6030", "6045"].join("\n"),
		},
		{
			fieldname: "customer_type",
			label: __("客户类型"),
			fieldtype: "Select",
			options: ["", "快递网点", "外卖站点", "同城配送", "企业车队", "个人骑手"].join("\n"),
		},
		{
			fieldname: "lease_term",
			label: __("租期类型"),
			fieldtype: "Select",
			options: ["", "月租", "季租", "年租"].join("\n"),
		},
		{
			fieldname: "source_channel",
			label: __("获客渠道"),
			fieldtype: "Select",
			options: ["", "网点直签", "渠道代理", "地推活动", "老客推荐", "平台合作"].join("\n"),
		},
		{
			fieldname: "churn_reason",
			label: __("中止原因"),
			fieldtype: "Select",
			options: [
				"",
				"单价过高",
				"续航不足",
				"站点太远",
				"电池老旧",
				"押金与结算纠纷",
				"车辆淘汰",
				"竞品更低",
				"客户停业",
				"其他",
			].join("\n"),
		},
	],

	onload(report) {
		report.page.add_inner_message(
			__(
				"口径：中止率 = 当期中止客户 ÷ 期初在租客户；客户按客户编号去重；月租 = 单块月租 × 电池数。"
			)
		);
	},

	formatter(value, row, column, data, default_formatter) {
		let formatted = default_formatter(value, row, column, data);
		if (["net", "net_fee"].includes(column.fieldname) && value < 0) {
			formatted = `<span style="color:var(--red-500)">${formatted}</span>`;
		}
		if (column.fieldname === "churn_rate" && value > 8) {
			formatted = `<span style="color:var(--red-500);font-weight:600">${formatted}</span>`;
		}
		return formatted;
	},

	// 指标卡 + 3 张结构图：都在表格重绘后挂载
	after_datatable_render(report) {
		render_summary_cards(report);
		render_extra_charts(report);
	},
};

function render_extra_charts(report) {
	const chart = report.chart;
	if (!chart || !chart.data || !chart.data.extra_charts) {
		return;
	}
	const extra = chart.data.extra_charts;

	let container = document.getElementById("ug-extra-charts");
	if (!container) {
		container = document.createElement("div");
		container.id = "ug-extra-charts";
		container.style.display = "grid";
		container.style.gridTemplateColumns = "repeat(auto-fit, minmax(300px, 1fr))";
		container.style.gap = "16px";
		container.style.margin = "8px 0 16px";
		const anchor = report.chart.parentNode.parentNode;
		anchor.appendChild(container);
	}
	container.innerHTML = "";

	Object.keys(extra).forEach((key, index) => {
		const item = extra[key];
		if (!item || !item.labels || !item.labels.length) {
			return;
		}
		const card = document.createElement("div");
		card.style.background = "var(--card-bg, #fff)";
		card.style.border = "1px solid var(--border-color)";
		card.style.borderRadius = "8px";
		card.style.padding = "12px 12px 0";
		card.innerHTML = `<div style="font-weight:600;font-size:13px;margin-bottom:8px;color:var(--text-muted)">${item.title}</div>
			<div id="ug-extra-${key}" style="height:220px"></div>`;
		container.appendChild(card);

		setTimeout(() => {
			const el = document.getElementById(`ug-extra-${key}`);
			if (!el) return;
			const isDonut = item.type === "donut";
			new frappe.Chart(el, {
				data: { labels: item.labels, datasets: [{ name: item.title, values: item.values }] },
				type: isDonut ? "donut" : "bar",
				height: 220,
				colors: ["#22D3EE", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#60A5FA", "#F472B6", "#4ADE80"],
				barOptions: { spaceRatio: 0.4, horizontal: item.type === "bar-horizontal" },
			});
		}, 60 * (index + 1));
	});
}

// 指标卡渲染
function render_summary_cards(report) {
	const cards = report.report_summary || report.data?.report_summary || [];
	if (!cards || !cards.length) {
		return;
	}
	let container = document.getElementById("ug-summary-cards");
	if (!container) {
		container = document.createElement("div");
		container.id = "ug-summary-cards";
		container.style.display = "grid";
		container.style.gridTemplateColumns = "repeat(auto-fit, minmax(150px, 1fr))";
		container.style.gap = "12px";
		container.style.margin = "12px 0";
		report.chart.parentNode.parentNode.insertBefore(container, report.chart.parentNode);
	}

	const toneColor = {
		Green: "var(--green-500, #28a745)",
		Red: "var(--red-500, #dc3545)",
		Blue: "var(--blue-500, #2490ef)",
		Orange: "var(--orange-500, #ff8c00)",
		Grey: "var(--gray-500, #6c7680)",
	};

	container.innerHTML = cards
		.map((card) => {
			const color = toneColor[card.indicator] || "var(--text-color)";
			return `<div style="background:var(--card-bg,#fff);border:1px solid var(--border-color);border-radius:8px;padding:12px 14px">
				<div style="font-size:12px;color:var(--text-muted)">${card.label}</div>
				<div style="font-size:20px;font-weight:600;margin-top:6px;color:${color}">${card.value}</div>
			</div>`;
		})
		.join("");
}
