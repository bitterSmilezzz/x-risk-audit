#!/usr/bin/env python3
"""x-risk-audit 扫描器：对抓取的 X 数据跑 rules/sensitive-rules.json 里的规则。

用法:
    python3 risk_scan.py <data.json> [--own-handle HANDLE] [--out findings.tsv]
    python3 test_scan.py            # 回归测试（合成 fixtures，不碰真实数据）

输入 JSON（抓取器产物结构）:
    {
      "following": [ {u,t,d,l,s}, ... ],   # 「正在关注」时间线
      "myPosts":   [ {u,t,d,l,s}, ... ],   # 本人主页帖子
      "myReplies": [ {u,t,d,l,s}, ... ]    # 本人 with_replies（含互动对象原文）
    }
  也接受 {"groups": {"关注博主": [...], "我的帖子": [...], "我的回复": [...]}}。

字段: u=User-Name innerText(昵称/@handle/时间)  t=tweetText  d=time[datetime]  l=首个 a[href*="/status/"]  s=socialContext

规则来源: 与本脚本同级的 rules/sensitive-rules.json（与 Chrome 扩展共用的单一数据源）。
输出: TSV -> stdout（或 --out 文件）: 分组 / 类别 / 作者handle / 日期 / 命中词 / 帖子链接 / 正文摘要
      汇总数 -> stderr。无输入文件退出码 2。
"""
import argparse
import json
import re
import sys
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "sensitive-rules.json"

# check 字段的 Python 侧附加校验（JS 扩展侧按需另行实现）
def luhn_ok(num: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def valid_cn_id(num: str) -> bool:
    if len(num) != 18:
        return False
    y, m, d = int(num[6:10]), int(num[10:12]), int(num[12:14])
    return 1900 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31


CHECKS = {"luhn": luhn_ok, "cn_id": valid_cn_id}


def compile_rule(rule):
    flags = re.IGNORECASE if "i" in (rule.get("flags") or "") else 0
    return re.compile(rule["pattern"], flags)


def load_rules(path=RULES_PATH):
    if not path.exists():
        sys.exit(f"# 规则文件不存在: {path}")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    compiled = []
    for section in ("pii", "credentials", "topics"):
        for r in raw.get(section, []):
            compiled.append((section, r["label"], compile_rule(r), r.get("check")))
    return compiled


def handle_of(u: str) -> str:
    for line in (u or "").split("\n"):
        line = line.strip()
        if line.startswith("@"):
            return line
    return (u or "").split("\n")[0] or "?"


def load_groups(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "groups" in data:
        return data["groups"]
    known = {"following": "关注博主", "myPosts": "我的帖子", "myReplies": "我的回复"}
    return {known[k]: v for k, v in data.items() if k in known and isinstance(v, list)}


def scan(path: str, own_handle: str, rules=None):
    rules = rules or load_rules()
    groups = load_groups(path)
    own = own_handle.lower()
    findings = []
    for group, items in groups.items():
        own_only = group in ("我的帖子", "我的回复")
        for it in items:
            text = it.get("t") or ""
            url = it.get("l") or ""
            if own_only:
                if own and own not in url.lower():
                    continue  # with_replies 里混入的互动对象原文不计入本人内容
            elif own and own in url.lower():
                continue  # 关注流里偶尔出现自己的帖子，归到本人分组看
            if not text.strip():
                continue
            ts = (it.get("d") or "")[:10]
            who = handle_of(it.get("u", ""))
            for _section, label, rx, check in rules:
                for m in rx.finditer(text):
                    v = m.group(0)
                    fn = CHECKS.get(check)
                    if fn and not fn(v):
                        continue
                    findings.append((group, label, who, ts, v[:40], url, text[:80].replace("\n", "⏎")))
    return groups, findings


def main():
    ap = argparse.ArgumentParser(description="X 风控数据扫描器")
    ap.add_argument("data", nargs="?", default="x_risk_merged.json", help="合并后的抓取数据 JSON")
    ap.add_argument("--own-handle", default="yg6888", help="本人 X handle（不含 @），用于过滤本人内容")
    ap.add_argument("--out", help="TSV 输出文件（默认 stdout）")
    args = ap.parse_args()

    try:
        groups, findings = scan(args.data, args.own_handle)
    except FileNotFoundError:
        print(f"# 输入文件不存在: {args.data}", file=sys.stderr)
        sys.exit(2)

    lines = ["\t".join(f) for f in findings]
    out = "\n".join(lines) + ("\n" if lines else "")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)

    counts = {g: len(v) for g, v in groups.items()}
    print(f"# 扫描样本: {counts}", file=sys.stderr)
    print(f"# 命中 {len(findings)} 条（含误报，需人工复核）", file=sys.stderr)


if __name__ == "__main__":
    main()
