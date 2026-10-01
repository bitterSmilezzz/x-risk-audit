# x-risk-audit

对 X（Twitter）账号执行一轮**风控检测**的 Agent Skill：只读抓取「正在关注」时间线、本人发帖与回复，规则引擎扫描个人隐私、凭据密钥、敏感违规话题与诈骗引流内容，人工复核后输出分级处置报告。

一次真实检测的产物形态：关注流 195 条 → 9 条有效风险帖（执法传闻 / 极端暴力 / 种族歧视 / 色情低俗 / 刷粉机器人）；本人 13 条原创帖 + 30 余条回复零命中。

## 安全边界

- **只读**：不发帖、不点赞、不转发、不关注/取关。处置建议写进报告，由用户本人执行。
- **不代登录**：凭证属于用户操作；通道未登录时交还用户登录。
- **数据不出本机**：抓取数据只落本地并进 `.gitignore`；本仓库不含任何真实账号数据。

## 安装

把仓库内的 `x-risk-audit/` 目录（skill 本体）放进任一 skills 根目录：

```bash
# 方式一：克隆后软链
git clone https://github.com/bitterSmilezzz/x-risk-audit.git
ln -s "$PWD/x-risk-audit/x-risk-audit" "$HOME/.agents/skills/x-risk-audit"

# 方式二：直接拷贝
cp -R x-risk-audit/x-risk-audit "$HOME/.agents/skills/"
```

MiMo Desktop 用户也可放 `~/.config/mimocode/skills/x-risk-audit/`。

## 触发方式

对 Agent 说："帮我做一轮 X 风控检测" / "检查我关注的博主有没有发敏感信息" / "检查我发的帖子有没有涉及敏感信息" / "X 账号风险自查"。

## 工作原理

```
确认口径/范围(弹窗)
   → 接管已登录浏览器(Tabbit 优先，IAB 兜底)
   → 抓取：关注流(正在关注) + 本人帖子 + 本人回复
   → scripts/risk_scan.py 规则扫描
   → 人工复核误报
   → 分级处置报告
```

| 文件 | 内容 |
|---|---|
| [`SKILL.md`](x-risk-audit/SKILL.md) | Skill 本体：安全纪律、六步工作流、故障处置 |
| [`rules/sensitive-rules.json`](x-risk-audit/rules/sensitive-rules.json) | **规则单一数据源**：PII / 凭据 / 敏感话题三类规则，Python 扫描器与 Chrome 扩展共用，JS/Python 双兼容正则 |
| [`scripts/risk_scan.py`](x-risk-audit/scripts/risk_scan.py) | 扫描器：消费规则 JSON，含身份证日期校验 / 银行卡 Luhn / 推文 ID 排除 |
| [`scripts/test_scan.py`](x-risk-audit/scripts/test_scan.py) | 回归测试：33 条合成 fixtures 的冻结预期（`python3 scripts/test_scan.py`） |
| [`references/detection-rules.md`](x-risk-audit/references/detection-rules.md) | 规则全集：查什么、为什么、已知误报、定级口径 |
| [`references/x-scraping-playbook.md`](x-risk-audit/references/x-scraping-playbook.md) | X 抓取手册：关注流标签切换、虚拟滚动补捞、单程序落盘、quote tweet 陷阱 |
| [`references/report-template.md`](x-risk-audit/references/report-template.md) | 风控报告模板：六节骨架 + 填写要点 |
| [`extension/DESIGN.md`](extension/DESIGN.md) | Chrome 实时标记扩展架构方案（MV3，规划中） |

## 路线图

- [x] Skill：周期深度检测（抓取 → 规则扫描 → 分级报告）
- [x] Chrome 扩展：实时标记时间线敏感推文（M1–M3，v0.1.0）—— 架构见 [`extension/DESIGN.md`](extension/DESIGN.md)，与 skill 共用同一份规则 JSON

## Chrome 实时标记扩展（extension/）

刷 x.com 时命中敏感规则的推文当场描边 + 徽标（高=红 / 中=橙 / 低=黄），悬停看命中词与类别，popup 可总开关/分类开关/只看高风险，options 支持自定义关键词与规则导入导出。只读、零网络请求、推文内容不过服务器。

```bash
# 安装（开发者模式加载已解包扩展）
# Chrome → chrome://extensions → 打开开发者模式 → 加载已解包的扩展 → 选本仓库 extension/ 目录

# 规则同步：改规则只改 x-risk-audit/rules/sensitive-rules.json，然后
bash extension/sync-rules.sh

# 测试
node extension/test/test_scanner.mjs        # JS 扫描器 vs Python 冻结预期（34 条）
python3 x-risk-audit/scripts/test_scan.py   # Python 扫描器冻结预期
python3 extension/test/make-fixture-page.py # 生成仿 X 集成测试页（再起本地 http 服务打开验证）
```

**已在真实 x.com 实测通过**（2026-10-01，已登录会话）：初始扫描、滚动加载新推文实时标记、虚拟滚动旧标记移除、Observer 合成探针均正常。

**日常同步**（改规则后）：仓库内 `bash extension/sync-rules.sh` 同步进扩展包；加载实例 `~/extensions/x-risk-audit` 用
`rsync -a --delete <仓库>/extension/ ~/extensions/x-risk-audit/`。Chrome 会自动重载扩展，之后刷新 x.com 页面生效。popup/options 需在 chrome://extensions 手动点开验证（自动化无法操作 chrome:// 页面）。

## 依赖

- 抓取通道：Tabbit 浏览器（`tabbit-cli`）或 MiMo 内置浏览器；目标 X 账号已登录。
- 扫描器：Python 3.8+，无第三方依赖。

## License

MIT，见 [LICENSE](LICENSE)。
