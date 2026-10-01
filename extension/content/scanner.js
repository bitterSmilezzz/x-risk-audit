// 规则匹配引擎：与 Python 版 risk_scan.py 同语义。
// 规则来自 rules/sensitive-rules.json（JS/Python 双兼容正则；check 为附加校验）。
window.XRA = window.XRA || {};
(function () {
  const XRA = window.XRA;

  XRA.luhn = function luhn(num) {
    let total = 0;
    for (let i = 0; i < num.length; i++) {
      let d = num.charCodeAt(num.length - 1 - i) - 48;
      if (i % 2 === 1) {
        d *= 2;
        if (d > 9) d -= 9;
      }
      total += d;
    }
    return total % 10 === 0;
  };

  XRA.validCnId = function validCnId(num) {
    if (num.length !== 18) return false;
    const y = Number(num.slice(6, 10));
    const m = Number(num.slice(10, 12));
    const d = Number(num.slice(12, 14));
    return y >= 1900 && y <= 2030 && m >= 1 && m <= 12 && d >= 1 && d <= 31;
  };

  const CHECKS = { luhn: XRA.luhn, cn_id: XRA.validCnId };
  const SEV_ORDER = { high: 3, medium: 2, low: 1 };

  // customKeywords: options 页配置的自定义词（字符串数组），合并为一条 medium 级规则
  XRA.compileRules = function compileRules(rules, customKeywords) {
    const compiled = [];
    for (const section of ["pii", "credentials", "topics"]) {
      for (const r of rules[section] || []) {
        const flags = (r.flags || "").includes("i") ? "gi" : "g";
        try {
          compiled.push({
            id: r.id,
            label: r.label,
            section: section,
            severity: r.severity || "low",
            regex: new RegExp(r.pattern, flags),
            check: r.check || null,
          });
        } catch (e) {
          console.warn("[XRA] 规则编译失败:", r.id, e);
        }
      }
    }
    const words = (customKeywords || []).map((w) => String(w).trim()).filter(Boolean);
    if (words.length) {
      const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
      compiled.push({
        id: "custom-keyword",
        label: "自定义词",
        section: "custom",
        severity: "medium",
        regex: new RegExp(escaped, "g"),
        check: null,
      });
    }
    return compiled;
  };

  // 返回 [{label, section, severity, matched}]，语义与 Python 版逐条对齐
  XRA.scanText = function scanText(compiled, text) {
    if (!text) return [];
    const findings = [];
    for (const rule of compiled) {
      rule.regex.lastIndex = 0;
      let m;
      while ((m = rule.regex.exec(text)) !== null) {
        const value = m[0];
        const fn = CHECKS[rule.check];
        if (fn && !fn(value)) {
          if (rule.regex.lastIndex === m.index) rule.regex.lastIndex++;
          continue;
        }
        findings.push({ label: rule.label, section: rule.section, severity: rule.severity, matched: value });
        if (rule.regex.lastIndex === m.index) rule.regex.lastIndex++;
      }
    }
    return findings;
  };

  XRA.topSeverity = function topSeverity(findings) {
    let top = null;
    let topW = 0;
    for (const f of findings) {
      const w = SEV_ORDER[f.severity] || 1;
      if (w > topW) {
        topW = w;
        top = f.severity;
      }
    }
    return top;
  };
})();
