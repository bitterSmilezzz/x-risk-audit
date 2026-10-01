// 入口：加载规则与设置 → 初始扫描 → MutationObserver 监听时间线新推文。
// 无 chrome 环境（测试页）自动降级为默认设置 + 注入规则。
window.XRA = window.XRA || {};
(function () {
  const XRA = window.XRA;
  const DEFAULTS = {
    enabled: true,
    onlyHigh: false,
    sections: { pii: true, credentials: true, topics: true, custom: true },
    customKeywords: [],
  };

  let settings = Object.assign({}, DEFAULTS);
  let compiled = [];
  const findingsCache = new WeakMap();

  function articleText(article) {
    const el = article.querySelector(XRA.selectors.text);
    return el ? el.innerText : "";
  }

  function scanArticle(article) {
    if (!article || article.nodeType !== 1 || findingsCache.has(article)) return;
    const findings = XRA.scanText(compiled, articleText(article));
    findingsCache.set(article, findings);
    XRA.applyMark(article, findings, settings);
  }

  function scanNode(node) {
    if (!node || node.nodeType !== 1) return;
    if (node.matches && node.matches(XRA.selectors.tweet)) scanArticle(node);
    if (node.querySelectorAll) node.querySelectorAll(XRA.selectors.tweet).forEach(scanArticle);
  }

  function rescanAll() {
    document.querySelectorAll(XRA.selectors.tweet).forEach((a) => {
      XRA.applyMark(a, findingsCache.get(a) || [], settings);
    });
  }

  async function loadSettings() {
    try {
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.sync) {
        const got = await chrome.storage.sync.get(["settings"]);
        return Object.assign({}, DEFAULTS, got.settings || {});
      }
    } catch (e) {
      console.warn("[XRA] 设置读取失败，用默认值", e);
    }
    return Object.assign({}, DEFAULTS);
  }

  async function resolveRules() {
    const custom = await XRA.loadCustomRules();
    return custom || (await XRA.loadRules());
  }

  async function init() {
    XRA.injectStyles();
    settings = await loadSettings();
    const rules = await resolveRules();
    compiled = XRA.compileRules(rules, settings.customKeywords);

    document.querySelectorAll(XRA.selectors.tweet).forEach(scanArticle);

    const column = document.querySelector(XRA.selectors.timelineColumn) || document.body;
    const observer = new MutationObserver((mutations) => {
      for (const mu of mutations) {
        for (const n of mu.addedNodes) scanNode(n);
      }
    });
    observer.observe(column, { childList: true, subtree: true });

    document.addEventListener("xra:dismissed", rescanAll);

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
      chrome.storage.onChanged.addListener((changes, area) => {
        if (area === "sync" && changes.settings) {
          settings = Object.assign({}, DEFAULTS, changes.settings.newValue || {});
          compiled = XRA.compileRules(rules, settings.customKeywords);
          rescanAll();
        }
        if (area === "local" && (changes.customRules || changes.customKeywords)) {
          Promise.resolve(resolveRules()).then((r) => {
            compiled = XRA.compileRules(r, settings.customKeywords);
            document.querySelectorAll(XRA.selectors.tweet).forEach(scanArticle);
          });
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init());
  } else {
    init();
  }
})();
