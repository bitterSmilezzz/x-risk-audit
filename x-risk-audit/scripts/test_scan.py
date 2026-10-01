#!/usr/bin/env python3
"""x-risk-audit 回归测试：合成 fixtures + 冻结预期，不碰任何真实数据。

用法:
    python3 scripts/test_scan.py

冻结预期与 JS 测试（extension/test/test_scanner.mjs）共用
fixtures/expected_hits.json；改 rules/sensitive-rules.json 后两边都要跑。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "sample_posts.json"
EXPECTED_FILE = HERE / "fixtures" / "expected_hits.json"

spec = importlib.util.spec_from_file_location("risk_scan", HERE / "risk_scan.py")
risk_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk_scan)

# 冻结预期：status 链接 -> 应命中的类别集合（顺序无关）
_expectations = json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))
EXPECTED = {url: set(labels) for url, labels in _expectations["expectations"].items()}

# Python 侧独有：myReplies 按 own-handle 过滤，互动对象原文不得计入 findings
PARTNER_LINK = "https://x.com/sample_partner/status/9200000000000000003"


def main():
    _groups, findings = risk_scan.scan(str(FIXTURE), "yg6888")
    actual = {}
    for group, label, _who, _ts, _hit, url, _snip in findings:
        actual.setdefault(url, set()).add(label)

    failures = []
    for url, expected_labels in EXPECTED.items():
        if url == PARTNER_LINK:
            continue  # own-handle 过滤项，单独断言
        got = actual.get(url, set())
        if got != expected_labels:
            failures.append((url, sorted(expected_labels), sorted(got)))
    if PARTNER_LINK in actual:
        failures.append((PARTNER_LINK, "应被 own-handle 过滤", sorted(actual[PARTNER_LINK])))

    for url in set(actual) - set(EXPECTED):
        failures.append((url, "不在预期表内", sorted(actual[url])))

    total_expected = sum(len(v) for v in EXPECTED.values())
    if failures:
        print(f"FAIL: {len(failures)} 处不符")
        for url, exp, got in failures:
            print(f"  {url}\n    expected: {exp}\n    actual:   {got}")
        sys.exit(1)
    print(f"PASS: {len(EXPECTED)} 条 fixtures 全部符合冻结预期，共 {total_expected} 个命中")


if __name__ == "__main__":
    main()
