// Copyright (c) 2026, Interview Demo and contributors
// 用户增长数据大屏 —— 页面入口（Frappe Page 渲染时由 hooks.page_js 引入）
//
// ECharts 采用「同源静态资源 + 按需加载」：
// 随 App 分发（public/js/echarts.min.js），不依赖外网 CDN，离线内网环境也能点亮大屏。

const UG_ECHARTS_URL = "/assets/user_growth/js/echarts.min.js";
const UG_CSS_URL = "/assets/user_growth/css/user_growth_dashboard.css";

function ug_load_echarts() {
	return new Promise((resolve, reject) => {
		// v15 没有 page_css hook，样式在这里注入（幂等，重复进入页面不会重复加载）
		if (!document.querySelector(`link[href="${UG_CSS_URL}"]`)) {
			const link = document.createElement("link");
			link.rel = "stylesheet";
			link.href = UG_CSS_URL;
			document.head.appendChild(link);
		}
		if (window.echarts) return resolve();
		const el = document.createElement("script");
		el.src = UG_ECHARTS_URL;
		el.onload = resolve;
		el.onerror = () => reject(new Error("ECharts 加载失败: " + UG_ECHARTS_URL));
		document.head.appendChild(el);
	});
}

frappe.pages["user-growth-dashboard"].on_page_load = function (wrapper) {
	const $wrapper = typeof wrapper.jquery === "undefined" ? $(wrapper) : wrapper;
	ug_load_echarts()
		.then(() => new UserGrowthDashboard($wrapper))
		.catch((err) => {
			console.error(err);
			frappe.msgprint({ title: "大屏初始化失败", message: err.message, indicator: "red" });
		});
};

const UG_COLORS = ["#22D3EE", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#60A5FA", "#F472B6", "#4ADE80"];
const UG_MODEL_LABEL = { 4830: "48V30Ah", 6030: "60V30Ah", 6045: "60V45Ah" };

class UserGrowthDashboard {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "用户增长数据大屏",
			single_column: true,
		});
		this.range = 12;
		this.charts = {};
		this.countdown = 60;
		this.lastData = null;
		this.render_layout();
		this.bind_events();
		this.load_data();
		this.start_auto_refresh();
	}

	// ------------------------------------------------------------------
	// 布局：1920×1080 设计稿，按容器尺寸等比缩放
	// ------------------------------------------------------------------
	render_layout() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".page-body").css({ padding: 0, margin: 0, overflow: "hidden" });

		this.$viewport = $(`<div class="ug-viewport">
			<div class="ug-stage" id="ug-stage">
				<header class="ug-header">
					<div class="ug-header-left">
						<span class="ug-logo"></span>
						<span class="ug-title">用户增长数据大屏</span>
						<span class="ug-subtitle">租电业务 · 开通 / 中止 / 在租资产</span>
					</div>
					<div class="ug-header-right">
						<span class="ug-badge" id="ug-range-label">近 12 个月</span>
						<span class="ug-clock" id="ug-clock">--:--:--</span>
						<span class="ug-updated" id="ug-updated">等待数据…</span>
					</div>
				</header>

				<section class="ug-kpi-row" id="ug-kpi-row"></section>

				<section class="ug-main">
					<div class="ug-col">
						<div class="ug-card">
							<div class="ug-card-title">增长趋势<span class="ug-card-desc">新增 / 中止 / 净增长</span></div>
							<div class="ug-chart" id="chart-trend"></div>
						</div>
						<div class="ug-card">
							<div class="ug-card-title">获客渠道 TOP<span class="ug-card-desc">新增客户数</span></div>
							<div class="ug-rank" id="rank-channel"></div>
						</div>
					</div>
					<div class="ug-col">
						<div class="ug-card">
							<div class="ug-card-title">在租电池结构<span class="ug-card-desc">按型号（块）</span></div>
							<div class="ug-chart" id="chart-battery"></div>
						</div>
						<div class="ug-card">
							<div class="ug-card-title">中止率健康度<span class="ug-card-desc">当期 ÷ 期初在租</span></div>
							<div class="ug-chart" id="chart-ring"></div>
						</div>
					</div>
					<div class="ug-col">
						<div class="ug-card">
							<div class="ug-card-title">中止原因分布<span class="ug-card-desc">按客户数</span></div>
							<div class="ug-chart" id="chart-reason"></div>
						</div>
						<div class="ug-card">
							<div class="ug-card-title">城市新增 TOP<span class="ug-card-desc">近 12 个月</span></div>
							<div class="ug-chart" id="chart-city"></div>
						</div>
					</div>
				</section>

				<section class="ug-footer">
					<div class="ug-live">
						<span class="ug-live-dot"></span>
						<span class="ug-live-label">实时动态</span>
						<div class="ug-ticker" id="ug-ticker"></div>
					</div>
					<div class="ug-refresh">
						<span id="ug-countdown">60s 后刷新</span>
						<button class="ug-btn" id="ug-btn-refresh">立即刷新</button>
						<button class="ug-btn" id="ug-btn-range">切换范围</button>
						<button class="ug-btn" id="ug-btn-fullscreen">全屏</button>
					</div>
				</section>

				<div class="ug-overlay" id="ug-overlay">
					<div class="ug-overlay-box">
						<div class="ug-spinner"></div>
						<div id="ug-overlay-text">正在加载增长数据…</div>
					</div>
				</div>
			</div>
		</div>`);

		this.wrapper.find(".page-body").append(this.$viewport);
		this.stage = this.$viewport.find("#ug-stage");

		const resize = () => {
			const host = this.$viewport[0];
			if (!host) return;
			const scale = Math.min(host.clientWidth / 1920, host.clientHeight / 1080);
			this.stage.css("transform", `translate(-50%, -50%) scale(${scale})`);
		};
		$(window).on("resize", resize);
		setTimeout(resize, 30);
		setTimeout(resize, 300);

		this.start_clock();
	}

	bind_events() {
		this.$viewport.on("click", "#ug-btn-refresh", () => this.load_data(true));
		this.$viewport.on("click", "#ug-btn-fullscreen", () => this.toggle_fullscreen());
		this.$viewport.on("click", "#ug-btn-range", () => {
			this.range = this.range === 24 ? 12 : this.range === 12 ? 6 : 24;
			this.load_data(true);
		});
	}

	toggle_fullscreen() {
		const el = this.$viewport[0];
		if (!document.fullscreenElement) {
			el.requestFullscreen?.();
		} else {
			document.exitFullscreen?.();
		}
		setTimeout(() => $(window).trigger("resize"), 400);
	}

	start_clock() {
		const pad = (n) => String(n).padStart(2, "0");
		const tick = () => {
			const now = new Date();
			this.$viewport
				.find("#ug-clock")
				.text(
					`${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
				);
		};
		tick();
		setInterval(tick, 1000);
	}

	// ------------------------------------------------------------------
	// 数据：单接口快照，保证 8 个区块属于同一帧
	// ------------------------------------------------------------------
	load_data(manual = false) {
		const first_load = !this.lastData;
		if (first_load) this.show_overlay();

		frappe
			.call({
				method: "user_growth.user_growth.utils.analytics.get_dashboard_snapshot",
				type: "GET",
				args: { months: this.range },
			})
			.then((res) => {
				const data = res.message;
				if (!data) throw new Error("empty snapshot");
				this.render(data);
				this.hide_overlay();
				this.$viewport.find(".ug-error-bar").remove();
				this.countdown = 60;
			})
			.catch((err) => {
				console.error(err);
				this.hide_overlay();
				this.show_error();
			});
	}

	show_overlay() {
		this.$viewport.find("#ug-overlay").addClass("show");
	}

	hide_overlay() {
		this.$viewport.find("#ug-overlay").removeClass("show");
	}

	show_error() {
		// 刷新失败：保留旧数据 + 顶部细红条，绝不白屏
		if (!this.$viewport.find(".ug-error-bar").length) {
			this.stage.prepend(`<div class="ug-error-bar">数据更新失败，将在 30 秒后自动重试</div>`);
			this.countdown = 30;
		}
	}

	start_auto_refresh() {
		setInterval(() => {
			this.countdown -= 1;
			this.$viewport.find("#ug-countdown").text(`${Math.max(this.countdown, 0)}s 后刷新`);
			if (this.countdown <= 0) {
				this.load_data(true);
			}
		}, 1000);
	}

	// ------------------------------------------------------------------
	// 渲染
	// ------------------------------------------------------------------
	render(data) {
		this.lastData = data;
		this.render_kpi(data.kpi);
		this.render_trend(data.trend);
		this.render_reason(data.reason_breakdown);
		this.render_city(data.city_rank);
		this.render_battery(data.battery_mix);
		this.render_ring(data.kpi);
		this.render_rank($("#rank-channel"), data.channel_rank, "#22D3EE");
		this.render_ticker(data.recent_events);
		this.$viewport.find("#ug-updated").text(`更新于 ${data.generated_at}`);
		this.$viewport.find("#ug-range-label").text(`近 ${data.months} 个月`);
	}

	render_kpi(kpi) {
		const fmt = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString());
		const pct = (v) => (v === null || v === undefined ? "—" : `${Number(v).toFixed(2)}%`);
		const money = (v) =>
			Math.abs(v) >= 10000 ? `${(v / 10000).toFixed(1)} 万` : Number(v).toLocaleString();

		const items = [
			{ label: "在租客户", value: fmt(kpi.active_customers), unit: "家", tone: "cyan" },
			{ label: "在租电池", value: fmt(kpi.active_battery), unit: "块", tone: "green" },
			{ label: "本月新增", value: `+${fmt(kpi.new_month)}`, unit: "家", tone: "green" },
			{ label: "本月中止", value: `-${fmt(kpi.churn_month)}`, unit: "家", tone: "red" },
			{ label: "净增长", value: fmt(kpi.net_month), unit: "家", tone: kpi.net_month >= 0 ? "green" : "red" },
			{ label: "中止率", value: pct(kpi.churn_rate), unit: "", tone: kpi.churn_rate > 8 ? "red" : "amber" },
			{ label: "在租月租", value: money(kpi.monthly_fee), unit: "元/月", tone: "cyan" },
			{ label: "未归还电池", value: fmt(kpi.unreturned_battery), unit: "块", tone: kpi.unreturned_battery ? "red" : "green" },
		];

		this.$viewport.find("#ug-kpi-row").html(
			items
				.map(
					(it) => `<div class="ug-kpi ug-kpi-${it.tone}">
						<div class="ug-kpi-label">${it.label}</div>
						<div class="ug-kpi-value">${it.value}<span class="ug-kpi-unit">${it.unit}</span></div>
					</div>`
				)
				.join("")
		);
	}

	chart(id, option) {
		const el = document.getElementById(id);
		if (!el) return;
		if (!this.charts[id]) {
			this.charts[id] = echarts.init(el, null, { renderer: "canvas" });
			window.addEventListener("resize", () => this.charts[id] && this.charts[id].resize());
		}
		this.charts[id].setOption(option, true);
	}

	render_trend(trend) {
		if (!trend || !trend.length) return;
		this.chart("chart-trend", {
			grid: { left: 40, right: 30, top: 34, bottom: 24 },
			tooltip: {
				trigger: "axis",
				backgroundColor: "rgba(8,20,34,.92)",
				borderColor: "#22D3EE",
				textStyle: { color: "#E6F6FF" },
			},
			legend: {
				data: ["新增", "中止", "净增长"],
				right: 6,
				top: 0,
				textStyle: { color: "#9BC3D9", fontSize: 11 },
				itemWidth: 10,
				itemHeight: 10,
			},
			xAxis: {
				type: "category",
				data: trend.map((t) => t.month.slice(2)),
				axisLine: { lineStyle: { color: "#1E3A52" } },
				axisLabel: { color: "#7FA5BC", fontSize: 10 },
			},
			yAxis: {
				type: "value",
				splitLine: { lineStyle: { color: "rgba(30,58,82,.5)" } },
				axisLabel: { color: "#7FA5BC", fontSize: 10 },
			},
			series: [
				{
					name: "新增",
					type: "bar",
					data: trend.map((t) => t.new),
					barWidth: 10,
					itemStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
							{ offset: 0, color: "#22D3EE" },
							{ offset: 1, color: "rgba(34,211,238,.15)" },
						]),
						borderRadius: [3, 3, 0, 0],
					},
				},
				{
					name: "中止",
					type: "bar",
					data: trend.map((t) => t.churn),
					barWidth: 6,
					itemStyle: { color: "#F87171", borderRadius: [2, 2, 0, 0] },
				},
				{
					name: "净增长",
					type: "line",
					smooth: true,
					symbol: "circle",
					symbolSize: 5,
					data: trend.map((t) => t.net),
					lineStyle: { width: 2, color: "#34D399" },
					itemStyle: { color: "#34D399" },
					areaStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
							{ offset: 0, color: "rgba(52,211,153,.28)" },
							{ offset: 1, color: "rgba(52,211,153,0)" },
						]),
					},
				},
			],
		});
	}

	render_reason(list) {
		if (!list || !list.length) return;
		this.chart("chart-reason", {
			tooltip: {
				trigger: "item",
				backgroundColor: "rgba(8,20,34,.92)",
				borderColor: "#F87171",
				textStyle: { color: "#E6F6FF" },
			},
			legend: {
				type: "scroll",
				orient: "vertical",
				right: 2,
				top: "middle",
				textStyle: { color: "#9BC3D9", fontSize: 10 },
				itemWidth: 8,
				itemHeight: 8,
			},
			series: [
				{
					type: "pie",
					radius: ["40%", "66%"],
					center: ["35%", "52%"],
					roseType: "radius",
					data: list.map((x, i) => ({
						name: x.label,
						value: x.value,
						itemStyle: { color: UG_COLORS[i % UG_COLORS.length] },
					})),
					label: { color: "#9BC3D9", fontSize: 9, formatter: "{b}\n{d}%" },
					labelLine: { length: 6, length2: 6, lineStyle: { color: "#2A4A66" } },
				},
			],
		});
	}

	render_city(list) {
		if (!list || !list.length) return;
		this.chart("chart-city", {
			grid: { left: 46, right: 28, top: 12, bottom: 8 },
			tooltip: {
				trigger: "axis",
				backgroundColor: "rgba(8,20,34,.92)",
				borderColor: "#22D3EE",
				textStyle: { color: "#E6F6FF" },
			},
			xAxis: {
				type: "value",
				splitLine: { lineStyle: { color: "rgba(30,58,82,.5)" } },
				axisLabel: { color: "#7FA5BC", fontSize: 10 },
			},
			yAxis: {
				type: "category",
				data: list.map((x) => x.label).reverse(),
				axisLine: { lineStyle: { color: "#1E3A52" } },
				axisLabel: { color: "#9BC3D9", fontSize: 11 },
			},
			series: [
				{
					type: "bar",
					data: list.map((x) => x.value).reverse(),
					barWidth: 12,
					itemStyle: {
						color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
							{ offset: 0, color: "rgba(34,211,238,.25)" },
							{ offset: 1, color: "#34D399" },
						]),
						borderRadius: [0, 6, 6, 0],
					},
					label: { show: true, position: "right", color: "#9BC3D9", fontSize: 10 },
				},
			],
		});
	}

	render_battery(list) {
		if (!list || !list.length) return;
		this.chart("chart-battery", {
			tooltip: {
				trigger: "item",
				backgroundColor: "rgba(8,20,34,.92)",
				borderColor: "#34D399",
				textStyle: { color: "#E6F6FF" },
			},
			series: [
				{
					type: "pie",
					radius: ["28%", "62%"],
					center: ["50%", "54%"],
					roseType: "area",
					itemStyle: { borderRadius: 6, borderColor: "rgba(4,14,26,.9)", borderWidth: 2 },
					data: list.map((x, i) => ({
						name: `${x.label} ${UG_MODEL_LABEL[x.label] || ""}`,
						value: x.value,
						itemStyle: { color: UG_COLORS[i % UG_COLORS.length] },
					})),
					label: { color: "#9BC3D9", fontSize: 10, formatter: "{b}\n{c} 块" },
				},
			],
		});
	}

	render_ring(kpi) {
		const rate = kpi.churn_rate || 0;
		this.chart("chart-ring", {
			series: [
				{
					type: "gauge",
					startAngle: 210,
					endAngle: -30,
					min: 0,
					max: 100,
					radius: "92%",
					progress: {
						show: true,
						width: 10,
						itemStyle: { color: rate > 8 ? "#F87171" : "#34D399" },
					},
					axisLine: { lineStyle: { width: 10, color: [[1, "rgba(34,211,238,.12)"]] } },
					axisTick: { show: false },
					splitLine: { show: false },
					axisLabel: { show: false },
					pointer: { show: false },
					anchor: { show: false },
					detail: {
						valueAnimation: true,
						formatter: () => `${rate.toFixed(1)}%`,
						color: "#E6F6FF",
						fontSize: 26,
						fontWeight: 700,
						offsetCenter: [0, "-2%"],
					},
					data: [{ value: Math.min(rate, 100) }],
				},
			],
			graphic: [
				{
					type: "text",
					left: "center",
					top: "70%",
					style: {
						text: `在租 ${kpi.active_customers} · 本月流失 ${kpi.churn_month}`,
						fill: "#7FA5BC",
						fontSize: 12,
					},
				},
			],
		});
	}

	render_rank($el, list, color) {
		if (!$el || !$el.length || !list || !list.length) return;
		const max = Math.max(...list.map((x) => x.value), 1);
		$el.html(
			list
				.map(
					(x, i) => `<div class="ug-rank-item">
						<span class="ug-rank-idx">${String(i + 1).padStart(2, "0")}</span>
						<span class="ug-rank-label">${x.label}</span>
						<span class="ug-rank-bar"><i style="width:${(x.value / max) * 100}%;background:linear-gradient(90deg,${color}55,${color})"></i></span>
						<span class="ug-rank-value">${x.value}</span>
					</div>`
				)
				.join("")
		);
	}

	render_ticker(events) {
		const $t = this.$viewport.find("#ug-ticker");
		if (!events || !events.length) {
			$t.html(`<div class="ug-ticker-item">暂无动态</div>`);
			return;
		}
		$t.html(
			events
				.map(
					(e) => `<div class="ug-ticker-item ug-ticker-${e.tag}">
						<span class="ug-tag">${e.type}</span>
						<span class="ug-ticker-text">${e.text}</span>
						<span class="ug-ticker-date">${e.date}</span>
					</div>`
				)
				.join("")
		);

		// 5 秒轮播一条，悬停暂停
		clearInterval(this.tickerTimer);
		const items = $t.children();
		if (items.length <= 1) return;
		let idx = 0;
		items.hide().eq(0).show();
		this.tickerTimer = setInterval(() => {
			idx = (idx + 1) % items.length;
			items.hide().eq(idx).fadeIn(200);
		}, 5000);
	}
}
