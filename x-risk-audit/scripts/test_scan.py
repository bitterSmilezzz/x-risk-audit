#!/usr/bin/env python3
"""x-risk-audit 回归测试：合成 fixtures + 冻结预期命中，不碰任何真实数据。

用法:
    python3 scripts/test_scan.py

改 rules/sensitive-rules.json 后必须跑一遍：
  - 只应该出现你有意为之的变化；
  - 不想变的行为被打破 = 规则改坏了，回滚。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "sample_posts.json"

spec = importlib.util.spec_from_file_location("risk_scan", HERE / "risk_scan.py")
risk_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk_scan)

# 冻结预期：status 链接 -> 应命中的类别集合（顺序无关）
EXPECTED = {
    # --- following ---
    "https://x.com/sample_alice/status/9000000000000000001": {"PII-中国手机号"},
    "https://x.com/sample_bob/status/9000000000000000002": {"PII-身份证号"},
    "https://x.com/sample_carol/status/9000000000000000003": {"PII-银行卡号"},
    "https://x.com/sample_dave/status/9000000000000000004": {"PII-电子邮箱"},
    "https://x.com/sample_eve/status/9000000000000000005": {"PII-地址门牌", "PII-住址关键词"},
    # 已知误报（叙事句，人工复核时排除）——规则按设计命中
    "https://x.com/sample_frank/status/9000000000000000006": {"PII-住址关键词"},
    # 19 位推文 snowflake ID：不得命中身份证/银行卡
    "https://x.com/sample_grace/status/9000000000000000007": set(),
    "https://x.com/sample_heidi/status/9000000000000000008": {"凭据-sk-密钥"},
    "https://x.com/sample_ivan/status/9000000000000000009": {"凭据-GitHubToken"},
    "https://x.com/sample_judy/status/9000000000000000010": {"凭据-AWSAccessKey"},
    # 私钥同时命中私钥规则与密钥赋值规则（纵深防御，符合预期）
    "https://x.com/sample_karl/status/9000000000000000011": {"凭据-私钥0x64hex", "凭据-密钥赋值"},
    "https://x.com/sample_laura/status/9000000000000000012": {"凭据-BearerJWT", "凭据-密钥赋值"},
    "https://x.com/sample_mallory/status/9000000000000000013": {"凭据-密钥赋值"},
    "https://x.com/sample_nick/status/9000000000000000014": {"话题-翻墙工具"},
    "https://x.com/sample_olivia/status/9000000000000000015": {"话题-极端言行"},
    "https://x.com/sample_pam/status/9000000000000000016": {"话题-歧视仇恨"},
    "https://x.com/sample_quinn/status/9000000000000000017": {"话题-诈骗引流"},
    "https://x.com/sample_rosa/status/9000000000000000018": {"话题-赌博博彩"},
    "https://x.com/sample_sam/status/9000000000000000019": {"话题-色情招嫖"},
    "https://x.com/sample_tina/status/9000000000000000020": {"话题-毒品"},
    "https://x.com/sample_ursula/status/9000000000000000021": {"话题-自残低俗"},
    "https://x.com/sample_victor/status/9000000000000000022": {"话题-政治敏感"},
    "https://x.com/sample_wendy/status/9000000000000000023": {"话题-敏感人物"},
    "https://x.com/sample_xavier/status/9000000000000000024": {"话题-暴恐极端"},
    "https://x.com/sample_yara/status/9000000000000000025": set(),
    "https://x.com/sample_zack/status/9000000000000000026": set(),
    "https://x.com/sample_alan/status/9000000000000000027": set(),
    # 19 位订单号：Luhn 挡掉银行卡，无其他粘连
    "https://x.com/sample_bella/status/9000000000000000028": set(),
    # --- myPosts ---
    "https://x.com/yg6888/status/9100000000000000001": set(),
    # 讨论密钥处理方法但无真实密钥串：不得命中
    "https://x.com/yg6888/status/9100000000000000002": set(),
    "https://x.com/yg6888/status/9100000000000000003": {"PII-中国手机号"},
    # --- myReplies ---
    "https://x.com/yg6888/status/9200000000000000001": set(),
    "https://x.com/yg6888/status/9200000000000000002": {"话题-极端言行"},
    # 9200000000000000003 是互动对象原文：own-handle 过滤后不得出现在 findings
}

PARTNER_LINK = "https://x.com/sample_partner/status/9200000000000000003"


def main():
    _groups, findings = risk_scan.scan(str(FIXTURE), "yg6888")
    actual = {}
    for group, label, _who, _ts, _hit, url, _snip in findings:
        actual.setdefault(url, set()).add(label)

    failures = []
    for url, expected_labels in EXPECTED.items():
        got = actual.get(url, set())
        if got != expected_labels:
            failures.append((url, sorted(expected_labels), sorted(got)))
    if PARTNER_LINK in actual:
        failures.append((PARTNER_LINK, "应被 own-handle 过滤", sorted(actual[PARTNER_LINK])))

    extra_urls = set(actual) - set(EXPECTED) - {PARTNER_LINK}
    for url in extra_urls:
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
