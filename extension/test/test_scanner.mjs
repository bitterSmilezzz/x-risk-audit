// JS 扫描器单测：与 Python 版 test_scan.py 共用 fixtures 与冻结预期。
// 用法: node extension/test/test_scanner.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));

// content 脚本是经典脚本（挂 window.XRA），在 Node 里把 window 指向全局后动态加载
globalThis.window = globalThis;
await import(pathToFileURL(path.join(here, "../content/rules.js")).href);
await import(pathToFileURL(path.join(here, "../content/scanner.js")).href);

function pathToFileURL(p) {
  return { href: "file://" + p };
}

const XRA = globalThis.XRA;
if (!XRA || !XRA.scanText) {
  console.error("FAIL: scanner 未加载");
  process.exit(1);
}

const rules = JSON.parse(readFileSync(path.join(here, "../rules/sensitive-rules.json"), "utf8"));
const fixtures = JSON.parse(
  readFileSync(path.join(here, "../../x-risk-audit/scripts/fixtures/sample_posts.json"), "utf8")
);
const { expectations } = JSON.parse(
  readFileSync(path.join(here, "../../x-risk-audit/scripts/fixtures/expected_hits.json"), "utf8")
);

const compiled = XRA.compileRules(rules, []);

let failures = 0;
let hitTotal = 0;
for (const group of ["following", "myPosts", "myReplies"]) {
  for (const item of fixtures[group] || []) {
    const expected = new Set(expectations[item.l] || []);
    if (!(item.l in expectations)) {
      console.error(`FAIL: ${item.l} 不在预期表内`);
      failures++;
      continue;
    }
    const findings = XRA.scanText(compiled, item.t);
    const got = new Set(findings.map((f) => f.label));
    hitTotal += got.size;
    const missing = [...expected].filter((x) => !got.has(x));
    const extra = [...got].filter((x) => !expected.has(x));
    if (missing.length || extra.length) {
      console.error(`FAIL: ${item.l}\n  missing: ${missing}\n  extra:   ${extra}`);
      failures++;
    }
  }
}

if (failures) {
  console.error(`FAIL: ${failures} 处不符`);
  process.exit(1);
}
console.log(`PASS: JS 扫描器与 Python 冻结预期一致（${Object.keys(expectations).length} 条，${hitTotal} 个命中）`);
