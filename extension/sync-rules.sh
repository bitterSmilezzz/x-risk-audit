#!/usr/bin/env bash
# 把 skill 的规则单一数据源同步进扩展包。改规则只改 x-risk-audit/rules/sensitive-rules.json，然后跑本脚本。
set -euo pipefail
SRC="$(cd "$(dirname "$0")/../x-risk-audit/rules" && pwd)/sensitive-rules.json"
DST="$(cd "$(dirname "$0")" && pwd)/rules/sensitive-rules.json"
cp "$SRC" "$DST"
echo "synced: $DST"
