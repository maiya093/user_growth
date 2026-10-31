app_name = "user_growth"
app_title = "User Growth"
app_publisher = "maiya093"
app_description = "用户（租电客户）服务开通 / 中止单据 + 用户增长分析报表 + 用户增长数据大屏"
app_email = "maiya093@users.noreply.github.com"
app_license = "mit"
app_version = "1.0.0"

required_apps = []

# 角色与工作区随 App 安装
fixtures = [
	{"dt": "Role", "filters": [["name", "in", ["Growth Operator", "Growth Manager"]]]},
	"user_growth/fixtures/workspace.json",
]

# 安装后自动生成演示数据（幂等）
after_install = "user_growth.setup.install.after_install"

# 迁移后兜底：站点被清空也能恢复演示数据
after_migrate = ["user_growth.setup.install.ensure_demo_data"]

# 大屏页面的前端资源（v15 仅有 page_js hook，JS 内联注入；CSS 由大屏 JS 动态注入）
page_js = {
	"user-growth-dashboard": "public/js/user_growth_dashboard.js",
}

# 允许通过 /api/method 直接调用（用于联调）
override_whitelisted_methods = {}
