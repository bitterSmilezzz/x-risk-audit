#!/usr/bin/env python3
"""生成浏览器集成测试页：用合成 fixtures 造一个仿 X 时间线结构的静态页，
并内联规则（file:// 下 fetch 受限，走 window.__XRA_RULES__ 注入）。

生成物（gitignore，不入库）:
    test/rules.inline.js
    test/fixture-page.html
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT = HERE.parent
REPO = EXT.parent

rules = json.loads((EXT / "rules" / "sensitive-rules.json").read_text(encoding="utf-8"))
fixtures = json.loads((REPO / "x-risk-audit/scripts/fixtures/sample_posts.json").read_text(encoding="utf-8"))

(EXT / "test" / "rules.inline.js").write_text(
    "window.__XRA_RULES__ = " + json.dumps(rules, ensure_ascii=False) + ";\n",
    encoding="utf-8",
)


def article(it):
    nick = (it.get("u") or "").split("\n")[0] or "someone"
    text = html.escape(it.get("t") or "").replace("\n", "<br>")
    return f"""<article data-testid="tweet">
  <div data-testid="User-Name"><span>{html.escape(nick)}</span><span>{(it.get('u') or '').split(chr(10))[1] if chr(10) in (it.get('u') or '') else ''}</span></div>
  <div data-testid="tweetText">{text}</div>
  <time datetime="{it.get('d') or ''}"></time>
  <a href="{it.get('l') or ''}">permalink</a>
</article>"""


items = fixtures["following"] + fixtures["myPosts"] + fixtures["myReplies"]
body = "\n".join(article(it) for it in items)

page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>XRA fixture page</title>
</head>
<body>
<div data-testid="primaryColumn" id="column">
{body}
</div>
<script src="rules.inline.js"></script>
<script src="../content/selectors.js"></script>
<script src="../content/rules.js"></script>
<script src="../content/scanner.js"></script>
<script src="../content/marker.js"></script>
<script src="../content/index.js"></script>
<script>
// 自检：在页面自己的脚本里做 DOM 变更（自动化 evaluate 是隔离世界，只能读 DOM），
// 结果写入 #xra-test-result 的 data-json 属性供只读读取。
var __XRA_DONE = false;
window.addEventListener("DOMContentLoaded", async () => {{
  await new Promise(r => setTimeout(r, 1000)); // 等 index.js init 完成
  const out = {{}};
  const XRA = window.XRA;
  const col = document.getElementById("column");

  // 1. Observer：动态插入一条命中的新推文
  const newArt = document.createElement("article");
  newArt.setAttribute("data-testid", "tweet");
  newArt.innerHTML = '<div data-testid="User-Name"><span>x</span><span>@x</span></div>' +
    '<div data-testid="tweetText">动态插入的新推文：同城招嫖联系我</div>' +
    '<time datetime="2026-10-01T15:00:00Z"></time><a href="/x/status/1">p</a>';
  col.appendChild(newArt);
  await new Promise(r => setTimeout(r, 600));
  out.observerMark = newArt.getAttribute("data-xra-marked") || null;
  out.observerBadge = newArt.querySelector(".xra-badge")?.textContent || null;

  // 2. 设置过滤：medium 文章在 onlyHigh / disabled / 恢复 三种设置下的标记
  const compiled = XRA.compileRules(window.__XRA_RULES__, []);
  const medArt = [...document.querySelectorAll('article[data-testid="tweet"]')]
    .find(a => (a.querySelector('[data-testid="tweetText"]')?.innerText || "").includes("sk-abcdef"));
  const findings = XRA.scanText(compiled, medArt.querySelector('[data-testid="tweetText"]').innerText);
  out.medBefore = medArt.getAttribute("data-xra-marked") || null;
  XRA.applyMark(medArt, findings, {{ enabled: true, onlyHigh: true, sections: {{ pii: true, credentials: true, topics: true }} }});
  out.medAfterOnlyHigh = medArt.getAttribute("data-xra-marked") || null;
  XRA.applyMark(medArt, findings, {{ enabled: false, sections: {{}} }});
  out.medAfterDisabled = medArt.getAttribute("data-xra-marked") || null;
  XRA.applyMark(medArt, findings, {{ enabled: true, onlyHigh: false, sections: {{ pii: true, credentials: true, topics: true }} }});
  out.medRestored = medArt.getAttribute("data-xra-marked") || null;

  // 3. 不再标记：dismissLabels 后对应类别标记移除
  XRA.dismissLabels(["话题-色情招嫖"]);
  await new Promise(r => setTimeout(r, 300));
  out.afterDismiss = [...document.querySelectorAll('article[data-testid="tweet"]')]
    .filter(a => (a.querySelector('[data-testid="tweetText"]')?.innerText || "").includes("招嫖"))
    .map(a => a.getAttribute("data-xra-marked") || null);

  const node = document.createElement("div");
  node.id = "xra-test-result";
  node.style.display = "none";
  node.setAttribute("data-json", JSON.stringify(out));
  document.body.appendChild(node);
  __XRA_DONE = true;
}});
</script>
</body>
</html>
"""
(EXT / "test" / "fixture-page.html").write_text(page, encoding="utf-8")
print(f"generated: {EXT / 'test' / 'fixture-page.html'}（{len(items)} 条模拟推文）")
