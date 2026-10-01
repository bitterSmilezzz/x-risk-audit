# X 抓取手册（x-scraping-playbook）

以 Tabbit（tabbit-cli）接管用户已登录的 X 为默认路径；IAB（共享 Node REPL `agent.browsers`）为兜底。所有操作只读。

## 0. 通道选择

```bash
# Tabbit：先建任务看清单，找 x.com 标签页
"$HOME/.local/bin/tabbit-cli" create --task "X 风控检测"
# 输出 JSON 的 tabs[] 里找 "url":"https://x.com/..." 的 tabId
```

- 有 X 标签页：`--tab <id>` 接管。只接管这一个，**不要碰用户其他标签页**。
- 没有 X 标签页：可以 `nodejs` 不带 `--tab` 让 tabbit 开新页再 `page.goto("https://x.com/home")`；若无登录态会跳登录页 → 交还用户登录（`reportIssue("AUTHENTICATION_REQUIRED")`，finish 保留页面，等用户说他登录好了再接管）。
- Tabbit 不可用时走 IAB：`agent.browsers.getForUrl("https://x.com/")` → `tabs.new()` → `goto`；未登录就把 visibility `set(true)` 显示窗口请用户登录，之后访问 `/home` 验证是否被重定向到 `/i/jf/onboarding`。

## 1. 抽取函数（三个页面通用）

每条推文取五个字段，映射成扫描器的 `{u,t,d,l,s}`：

```js
const extract = () => page.locator('article[data-testid="tweet"]').evaluateAll(arts => arts.map(a => {
  const q = (sel) => { const el = a.querySelector(sel); return el ? (el.innerText || "") : ""; };
  const timeEl = a.querySelector("time");
  const statusA = a.querySelector('a[href*="/status/"]');
  return {
    u: q('[data-testid="User-Name"]'),      // 昵称/@handle/相对时间
    t: q('[data-testid="tweetText"]'),      // 正文
    d: timeEl ? timeEl.getAttribute("datetime") : "",  // ISO 时间
    l: statusA ? statusA.href : "",         // 帖子永久链接（去重键）
    s: q('[data-testid="socialContext"]'),  // "X 已转帖" 等
  };
}));
```

## 2. 关注流（正在关注）

**第一课：`x.com/home` 默认是"为你推荐"**，混入非关注账号，口径错误。必须先点「正在关注」：

```js
await page.goto("https://x.com/home", { waitUntil: "domcontentloaded" });
await page.getByRole("tab", { name: /关注/ }).first().click();
await page.waitForTimeout(4000);
```

然后滚动抓取。**单程序完成、直接写文件**：

```js
const fs = await import("node:fs");
const seen = new Set(); const items = [];
const ingest = (arts) => { let added = 0;
  for (const a of arts) { const key = a.l || (a.u + "|" + a.d + "|" + a.t.slice(0, 40));
    if (!seen.has(key)) { seen.add(key); items.push(a); added++; } } return added; };
const extract = /* 见上 */;
await page.getByRole("tab", { name: /关注/ }).first().click();
await page.waitForTimeout(4000);
ingest(await extract());
let stagnant = 0;
for (let i = 0; i < 30 && stagnant < 6; i++) {
  await page.evaluate(() => window.scrollBy(0, 750));
  await page.waitForTimeout(1300);      // 等新推文渲染
  const added = ingest(await extract());
  await page.waitForTimeout(900);
  ingest(await extract());              // 虚拟滚动补捞
  if (added === 0) stagnant++; else stagnant = 0;
}
fs.writeFileSync("/ABS/PATH/x_follow_full.json", JSON.stringify(items));
return { total: items.length };
```

节奏：每轮 ≈2.2s，30 轮 ≈70s，受 `--timeout-ms` 180000 限制安全。时间范围越大轮数越多；"尽可能多"用 30 轮起步， stagnation 6 轮自动停。

## 3. 本人帖子与回复

- 帖子：`https://x.com/USERNAME`
- 回复：`https://x.com/USERNAME/with_replies`（回复页混入互动对象原文，扫描时按主账号过滤 status 链接）

同样单程序 + 稳定等待loop。**结尾判定**：连续 6 轮无新增才停——X 主页时间线到底后不再加载；若轮次内 count 在 5–12 之间反复横跳，是虚拟滚动在删旧节点，继续轮转即可，别急着判"到底"。

**quote tweet 陷阱**：主页时间线里，你引用别人的推文会把**原作者**渲染在 User-Name 里（如引用官方活动帖）。抽到原作者 ≠ 漏抓，按"引用的内容"归类，别算成账号本人帖子。

## 4. 数据合并

```bash
python3 - <<'PY'
import json
base = json.load(open("x_risk_scan.json"))     # myPosts/myReplies（单次抓取落盘的那份）
full = json.load(open("x_follow_full.json"))   # 关注流
extra = json.load(open("x_follow_extra.json")) # 如有补录
seen, merged = set(), []
for it in full + extra:
    key = it.get("l") or (it.get("u","") + it.get("d","") + (it.get("t") or "")[:40])
    if key not in seen:
        seen.add(key); merged.append(it)
json.dump({"following": merged, "myPosts": base["myPosts"], "myReplies": base["myReplies"]},
          open("x_risk_merged.json","w"), ensure_ascii=False)
PY
python3 scripts/risk_scan.py x_risk_merged.json --own-handle <handle> --out findings.tsv
```

关注流非严格时间序，且边抓边刷新：**多轮抓取要合并去重**；漏抓个别帖子不影响"有没有敏感信息"的结论，报告里注明覆盖窗口即可。

## 5. 已知坑（都踩过）

| 坑 | 现象 | 解法 |
|---|---|---|
| 首页默认推荐流 | 混入非关注账号，口径错 | 必点「正在关注」标签 |
| 跨调用全局变量 | 后一次调用发现早前 2 条数据消失 | 单程序内累积并 writeFileSync，别信 globalThis 跨调用 |
| 花体 Unicode | 数学字母数字符号推文让 `write` 工具解析失败 | 用 Python heredoc 落盘，别过手写 |
| 429 限流 | finish 报告 `SITE_RATE_LIMITED` | 滚动间隔加大；告知用户无害 |
| 转载上下文 | `socialContext` 为"X 已转帖"时正文是原推文 | 标注为转帖，作者按原推文算 |
| 推文 ID 误判 PII | 19 位 snowflake 命中身份证/银行卡正则 | 脚本已做长度/校验排除，仍抽查 |

## 6. 清理

```bash
"$HOME/.local/bin/tabbit-cli" finish --task "X 风控检测"   # 释放接管、保留用户标签页
```

IAB 通道：关掉本任务 `tabs.new()` 出来的标签页，保留用户原有标签页。抓取数据文件只在本地，进 `.gitignore`，不提交。
