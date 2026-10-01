// 标记 UI：三强度描边 + 徽标 + 悬停详情。只标记不改写、不遮挡推文原文。
window.XRA = window.XRA || {};
(function () {
  const XRA = window.XRA;
  XRA.MARKED_ATTR = "data-xra-marked";
  XRA.BADGE_CLASS = "xra-badge";
  const dismissed = new Set(); // 本次会话不再标记的类别

  const CSS = `
.xra-mark{position:relative;border-radius:12px;outline:2px solid;outline-offset:2px;}
.xra-mark-high{outline-color:#e0245e;}
.xra-mark-medium{outline-color:#f5a623;}
.xra-mark-low{outline-color:#8a9ab0;}
.xra-badge{position:absolute;top:6px;right:6px;z-index:5;display:inline-flex;align-items:center;
  gap:4px;padding:1px 8px;border-radius:999px;font:11px/1.6 -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
  color:#fff;cursor:help;user-select:none;box-shadow:0 1px 3px rgba(0,0,0,.25);}
.xra-badge-high{background:#e0245e;}
.xra-badge-medium{background:#f5a623;}
.xra-badge-low{background:#8a9ab0;}
.xra-tip{position:absolute;z-index:9999;max-width:320px;padding:8px 10px;border-radius:8px;
  background:#1c2732;color:#e7e9ea;font:12px/1.6 -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
  box-shadow:0 4px 16px rgba(0,0,0,.4);pointer-events:none;}
.xra-tip-row{display:flex;justify-content:space-between;gap:12px;}
.xra-tip-cat{color:#8b98a5;}
.xra-tip-dismiss{margin-top:6px;color:#1d9bf0;cursor:pointer;pointer-events:auto;}
.xra-tip-dismiss:hover{text-decoration:underline;}
`;

  XRA.injectStyles = function injectStyles() {
    if (document.getElementById("xra-styles")) return;
    const style = document.createElement("style");
    style.id = "xra-styles";
    style.textContent = CSS;
    (document.head || document.documentElement).appendChild(style);
  };

  let tipEl = null;
  function hideTip() {
    if (tipEl && tipEl.parentNode) tipEl.parentNode.removeChild(tipEl);
    tipEl = null;
  }
  function showTip(badge, findings) {
    hideTip();
    const rows = findings.map((f) => `<div class="xra-tip-row"><span>${escapeHtml(f.matched.slice(0, 24))}</span><span class="xra-tip-cat">${escapeHtml(f.label)}</span></div>`).join("");
    const uniqLabels = [...new Set(findings.map((f) => f.label))];
    tipEl = document.createElement("div");
    tipEl.className = "xra-tip";
    tipEl.innerHTML = rows + `<div class="xra-tip-dismiss">本次会话不再标记: ${escapeHtml(uniqLabels.join(" / "))}</div>`;
    tipEl.querySelector(".xra-tip-dismiss").addEventListener("click", () => {
      XRA.dismissLabels(uniqLabels);
      hideTip();
    });
    document.body.appendChild(tipEl);
    const r = badge.getBoundingClientRect();
    tipEl.style.top = window.scrollY + r.bottom + 6 + "px";
    tipEl.style.left = window.scrollX + Math.max(8, r.left - 160) + "px";
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  XRA.dismissLabels = function dismissLabels(labels) {
    for (const l of labels) dismissed.add(l);
    document.dispatchEvent(new CustomEvent("xra:dismissed", { detail: { labels } }));
  };

  XRA.filterBySettings = function filterBySettings(findings, settings) {
    if (!settings || settings.enabled === false) return [];
    return findings.filter((f) => {
      if (settings.onlyHigh && f.severity !== "high") return false;
      if (settings.sections && settings.sections[f.section] === false) return false;
      if (dismissed.has(f.label)) return false;
      return true;
    });
  };

  // applyMark: 按设置对单条推文应用/移除标记；findings 为全量扫描结果
  XRA.applyMark = function applyMark(article, findings, settings) {
    if (!article) return;
    const shown = XRA.filterBySettings(findings, settings);
    article.classList.remove("xra-mark", "xra-mark-high", "xra-mark-medium", "xra-mark-low");
    const oldBadge = article.querySelector("." + XRA.BADGE_CLASS);
    if (oldBadge) oldBadge.remove();
    article.removeAttribute(XRA.MARKED_ATTR);
    if (!shown.length) return;

    const severity = XRA.topSeverity(shown) || "low";
    article.classList.add("xra-mark", "xra-mark-" + severity);
    article.setAttribute(XRA.MARKED_ATTR, severity);

    const badge = document.createElement("span");
    badge.className = XRA.BADGE_CLASS + " xra-badge-" + severity;
    const sevText = { high: "高风险", medium: "中风险", low: "提示" }[severity];
    badge.textContent = `${sevText} ${shown.length}`;
    badge.addEventListener("mouseenter", () => showTip(badge, shown));
    badge.addEventListener("mouseleave", hideTip);
    article.appendChild(badge);
  };
})();
