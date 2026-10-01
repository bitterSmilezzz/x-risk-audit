#!/usr/bin/env python3
"""x-risk-audit 扫描器：对抓取的 X 数据跑 PII / 凭据 / 敏感话题 / 诈骗引流规则。

用法:
    python3 risk_scan.py <data.json> [--own-handle HANDLE] [--out findings.tsv]

输入 JSON（抓取器产物结构）:
    {
      "following": [ {u,t,d,l,s}, ... ],   # 「正在关注」时间线
      "myPosts":   [ {u,t,d,l,s}, ... ],   # 本人主页帖子
      "myReplies": [ {u,t,d,l,s}, ... ]    # 本人 with_replies（含互动对象原文）
    }
  也接受 {"groups": {"关注博主": [...], "我的帖子": [...], "我的回复": [...]}}。

字段: u=User-Name innerText(昵称/@handle/时间)  t=tweetText  d=time[datetime]  l=首个 a[href*="/status/"]  s=socialContext

输出: TSV -> stdout（或 --out 文件）: 分组 / 类别 / 作者handle / 日期 / 命中词 / 帖子链接 / 正文摘要
      汇总数 -> stderr。退出码 0；无输入文件退出码 2。
"""
import argparse
import json
import re
import sys

MW = r"(?<!\d)"
NL = r"(?!\d)"

PII_RULES = [
    ("PII-中国手机号", re.compile(MW + r"1[3-9]\d{9}" + NL), None),
    ("PII-身份证号", re.compile(MW + r"\d{17}[\dXx]" + NL), "cn_id"),
    ("PII-银行卡号", re.compile(MW + r"\d{16,19}" + NL), "luhn"),
    ("PII-电子邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), None),
    ("PII-地址门牌", re.compile(r"(?:路|街|巷|道|弄|号|栋|单元|室|层)\s*\d+"), None),
    ("PII-住址关键词", re.compile(r"(?:我家在|住在|地址是|收货地址|现居|家住)[^\n。]{0,30}"), None),
]

CRED_RULES = [
    ("凭据-sk-密钥", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("凭据-GoogleAPIKey", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("凭据-GitHubToken", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("凭据-AWSAccessKey", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("凭据-SlackToken", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}")),
    ("凭据-私钥0x64hex", re.compile(r"\b0x[a-fA-F0-9]{64}\b")),
    ("凭据-BearerJWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    (
        "凭据-密钥赋值",
        re.compile(
            r"(?i)(?:api[_\-]?key|apikey|access[_\-]?token|secret|passwd|password|pwd|bearer"
            r"|私钥|密钥|密码|令牌|访问凭证|授权码)\s*[:=：是为]?\s*[\"']?[A-Za-z0-9_\-]{10,}"
        ),
    ),
]

TOPIC_RULES = [
    ("话题-政治敏感", re.compile(r"六四|天安门事件|法[轮輪][功功]|疆独|藏独|台独|港独|反送中|推翻共产党|颠覆国家|暴政|独裁政权|中共倒台|反动派|民运人士|反革命")),
    ("话题-敏感人物", re.compile(r"习近平|李克强|胡锦涛|温家宝|江泽民|毛泽东|邓小平|彭丽媛|薄熙来")),
    ("话题-翻墙工具", re.compile(r"科学上网|翻墙|梯子|机场订阅|节点订阅|clash|v2ray|shadowrocket|trojan|vpn", re.I)),
    ("话题-赌博博彩", re.compile(r"博彩|菠菜|网赌|时时彩|快三|百家乐|六合彩|跑分|资金盘|杀猪盘|赌狗")),
    ("话题-色情招嫖", re.compile(r"约炮|招嫖|嫖娼|援交|裸聊|色情直播|黄播|福利姬|卖淫|嫖客|卖片")),
    ("话题-毒品", re.compile(r"冰毒|大麻|海洛因|k粉|摇头丸|贩毒|吸毒|罂粟")),
    ("话题-暴恐极端", re.compile(r"炸药|炸弹|爆炸物|圣战|isis|恐怖袭击|灭门|砍杀|报复社会|推翻政府|武装斗争")),
    ("话题-极端言行", re.compile(r"毒死|暗杀|砍死|杀光|屠[杀村]|活该|去死")),
    ("话题-自残低俗", re.compile(r"直播吃|吃屎|自残|割腕|烧炭|跳楼自|轻生|直播自杀")),
    ("话题-歧视仇恨", re.compile(r"老黑|黑鬼|倪哥|支那|黄祸|纳粹|母猪|田园女权|easy girl|easygirl")),
    ("话题-诈骗引流", re.compile(r"稳赚|保底收益|日入|月入过万|免费领取|空投|airdrop|私信我|加微信|加我v|vx[:：]|telegram|飞机号|刷粉|买粉|互粉群|引流|connect wallet|claim now|verify your wallet|保证涨粉|boost your page", re.I)),
]


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
    known = {
        "following": "关注博主",
        "myPosts": "我的帖子",
        "myReplies": "我的回复",
    }
    return {known[k]: v for k, v in data.items() if k in known and isinstance(v, list)}


def scan(path: str, own_handle: str):
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
            for label, rx, check in PII_RULES:
                for m in rx.finditer(text):
                    v = m.group(0)
                    if check == "cn_id" and not valid_cn_id(v):
                        continue
                    if check == "luhn" and not luhn_ok(v):
                        continue
                    findings.append((group, label, who, ts, v[:40], url, text[:80].replace("\n", "⏎")))
            for label, rx in CRED_RULES:
                for m in rx.finditer(text):
                    findings.append((group, label, who, ts, m.group(0)[:40], url, text[:80].replace("\n", "⏎")))
            for label, rx in TOPIC_RULES:
                m = rx.search(text)
                if m:
                    findings.append((group, label, who, ts, m.group(0)[:20], url, text[:80].replace("\n", "⏎")))
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
