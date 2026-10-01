# Chrome 扩展架构方案 — X 实时敏感信息标记

> 状态：**M1–M3 已实现（v0.1.0，2026-10-01）**。本文档保留为架构与设计决策记录。
> 目标形态：装在 Chrome 上的 MV3 扩展，在 x.com 页面里**实时**扫描时间线推文，命中敏感规则的推文**就地标记**（描边 + 徽标 + 悬停详情），与 skill 的周期深度检测互补。
>
> 实现情况：manifest + content（selectors/rules/scanner/marker/index）+ popup + options + sync 脚本齐全；JS 扫描器与 Python 扫描器共用 fixtures 冻结预期（34 条全过）；浏览器集成测试通过（初始标记 26/34、Observer 动态标记、onlyHigh/禁用/恢复三态、不再标记）。

## 1. 定位与边界

| 维度 | 规则 |
|---|---|
| 能力 | 只读 DOM + 本地标记。**不发起任何网络请求、不调用任意 X API、不代替用户做任何账号操作**（不点赞/转评/关注/举报） |
| 隐私 | 推文内容只在内存中过规则，**不落盘、不上传、不记日志**；chrome.storage 只存用户配置（开关、自定义词） |
| 与 skill 的关系 | skill = 周期性深度检测（滚动抓全量 + 分级报告）；扩展 = 实时浅标记（刷到即标）。两者**共用 `rules/sensitive-rules.json` 同一份规则** |
| 分发 | `chrome://extensions` 开发者模式加载已解包扩展，个人自用，不进商店 |

## 2. 形态与架构

```
extension/
├── manifest.json            # MV3
├── content/
│   ├── index.js             # 入口：初始扫描 + MutationObserver 监听时间线
│   ├── selectors.js         # X DOM 选择器集中处（页面改版只改这里）
│   ├── rules.js             # 加载并编译 rules/sensitive-rules.json（fetch chrome.runtime.getURL）
│   ├── scanner.js           # 规则匹配（JS 侧 matchAll + check 简易实现）
│   └── marker.js            # 标记 UI：描边/徽标/tooltip/降级
├── rules/
│   └── sensitive-rules.json # 由同步脚本从 skill 复制，勿手改
├── popup/                   # 工具栏弹窗：总开关、分类开关、只看高风险
├── options/                 # 设置页：自定义关键词、导入/导出规则
└── sync-rules.sh            # cp ../x-risk-audit/rules/sensitive-rules.json rules/
```

数据流：

```
x.com timeline DOM
  → MutationObserver(capture: timeline 容器, childList+subtree)
  → selectors.js 抽出 article[data-testid="tweet"] 的 {text, statusUrl}
  → rules.js 已编译规则（启动时 fetch rules JSON 一次，缓存）
  → scanner.js 逐规则 matchAll → [{label, severity, matched}]
  → marker.js 在 article 上加 class + 徽标 + tooltip（dataset 打标防重复）
```

## 3. 关键设计点

**3.1 规则单一数据源**。扩展 `fetch(chrome.runtime.getURL('rules/sensitive-rules.json'))` 运行时加载；仓库里放 `sync-rules.sh` 把 skill 的规则复制进来。规则 `pattern` 已按 JS/Python 双兼容编写（lookbehind V8 支持；无 `(?i)` 内联标志，大小写不敏感走 `flags: "i"`）。JS 侧用 `new RegExp(pattern, 'g' + (flags||''))` + `matchAll`。

**3.2 `check` 字段的 JS 侧处理**。Python 有 `cn_id`（出生日期合法性）和 `luhn`（银行卡校验）两个附加校验挡误报。JS 侧两个选择：M1 先只实现 luhn（防推文 ID 误报，必须有）；`cn_id` 日期校验逻辑简单（约 10 行），一并移植。二者都放进 `scanner.js`，与 Python 版保持同语义。

**3.3 标记 UI（三强度，参考内容审核工具）**

| 强度 | 视觉 | 对应类别 |
|---|---|---|
| 高 | 红色描边 + 红徽标（命中数） | 政治敏感 / 敏感人物 / 翻墙工具（执法传闻类）/ 暴恐 / 极端言行 / 歧视仇恨 |
| 中 | 橙色描边 + 橙徽标 | 凭据密钥 / 色情招嫖 / 赌博 / 毒品 / 自残低俗 / 自定义词 |
| 低 | 黄色描边 + 灰徽标 | 个人隐私（PII）/ 诈骗引流模板 |

severity 定义在 `x-risk-audit/rules/sensitive-rules.json` 每条规则的 `severity` 字段，与规则同源，不在此硬编码。

徽标悬停出 tooltip：类别、命中词（打码展示）、该推文 status 链接。可一键"本次会话不再标记此类"。**不改写、不遮挡推文原文**。

**3.4 防重复与性能**。每条 article 处理后 `article.dataset.xraDone = "1"`，Observer 只处理新节点；规则编译一次缓存；regex 匹配同步执行（一条推文 ×25 条规则，微秒级），无需 debounce 匹配本身，但 Observer 回调用 `requestIdleCallback` 合批。X 虚拟滚动会反复插删节点，打标要跟随节点（节点被销毁重建则重新匹配，代价可接受）。

**3.5 页面改版降级**。`selectors.js` 集中所有 `data-testid` 选择器；若某次改版后选择器大面积失效（连续 N 个新 article 抽不到 text），content script 静默停标并在 popup 显示"选择器可能失效"，**不报错不干扰浏览**。

**3.6 不做清单**。不自动折叠/隐藏推文（只标记）；不提交任何"这是否违规"的判定到外部；不读取页面以外的东西（不碰 localStorage 里的 X 数据、不读 cookie）。

## 4. 里程碑（已完成）

- [x] **M1 最小可用**：manifest + content（Observer + 选择器 + 规则加载 + 标记描边/徽标）+ popup 总开关。
- [x] **M2 体验**：三强度配色、悬停 tooltip（命中词 + 类别 + 本次会话不再标记）、分类开关、"只看高风险"、options 自定义关键词与规则导入/导出。
- [x] **M3 联调**：`sync-rules.sh` 固化；JS 与 Python 扫描器共用 `scripts/fixtures/` 的冻结预期，两边测试同表（34 条，29 命中，全过）；浏览器集成测试（`test/make-fixture-page.py` 生成仿 X 页面）验证初始标记、Observer、设置过滤、dismiss。

## 5. 实现说明（踩过的点）

- **IAB evaluate 是隔离 JS 世界**：自动化通道只能读 DOM，读不到页面的 `window.XRA`。集成测试因此把自检结果写进 DOM 节点（`#xra-test-result[data-json]`）再读；测试页的 DOM 变更也必须由页面自己的脚本做。
- **file:// 被 IAB 导航策略拦截**：测试走本地 `python3 -m http.server`。
- **规则 JSON 的 `(?i)` 内联标志 JS 不支持**：统一走 flags 字段。
- **marker.js 修过一次重复声明**（`uniqLabels`）：`node --check` 全部 7 个 JS 文件是发布前必跑项。
- **推文 ID 19 位 vs 身份证 18 位**：JS/Python 双侧都有长度与 Luhn/日期校验，fixtures 有专项用例。

## 6. 已知风险

1. **X 页面改版**：选择器失效 → 降级策略见 3.5；`data-testid="tweet"` 比 class 稳定，以它为主锚。
2. **平台政策**：content script 纯只读、零网络，属浏览器本地增强，不构成自动化操作（auto-like/follow 才是高压线，明确不做）。
3. **误报打扰**：三强度配色 + 分类开关 + "不再标记此类"已控制；PII/凭据类默认对"本人时间线"最有用，可在 options 分页面开关。
4. **性能**：长会话推文量大时 Observer 合批 + 节点销毁即清理，预期无感；若实测掉帧再上 IntersectionObserver 只标可见区。

## 7. 与 skill 的分工

| | skill（已交付） | 扩展（本方案） |
|---|---|---|
| 触发 | 用户说"做一轮风控检测" | 常驻，刷到即标 |
| 范围 | 关注流全量 + 本人帖 + 回复 | 当前页面可见时间线 |
| 产出 | 分级报告 + 处置建议 | 就地标记 + tooltip |
| 规则 | `x-risk-audit/rules/sensitive-rules.json` | 同一文件，`sync-rules.sh` 同步 |
