// 规则加载：优先测试注入的 window.__XRA_RULES__，其次扩展包内 rules/sensitive-rules.json。
// 规则由 sync-rules.sh 从 skill 同步，勿手改 extension/rules/ 下的副本。
window.XRA = window.XRA || {};
window.XRA.loadRules = async function loadRules() {
  if (window.__XRA_RULES__) return window.__XRA_RULES__;
  const hasChrome = typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.getURL;
  if (hasChrome) {
    const res = await fetch(chrome.runtime.getURL("rules/sensitive-rules.json"));
    if (!res.ok) throw new Error("rules http " + res.status);
    return res.json();
  }
  throw new Error("rules unavailable: 无 chrome.runtime 且无注入规则");
};

window.XRA.loadCustomRules = async function loadCustomRules() {
  const hasChrome = typeof chrome !== "undefined" && chrome.storage && chrome.storage.local;
  if (!hasChrome) return null;
  const got = await chrome.storage.local.get(["customRules"]);
  return got.customRules || null;
};

window.XRA.saveCustomRules = async function saveCustomRules(rulesJson) {
  const hasChrome = typeof chrome !== "undefined" && chrome.storage && chrome.storage.local;
  if (!hasChrome) throw new Error("chrome.storage.local 不可用");
  await chrome.storage.local.set({ customRules: rulesJson });
};

window.XRA.clearCustomRules = async function clearCustomRules() {
  const hasChrome = typeof chrome !== "undefined" && chrome.storage && chrome.storage.local;
  if (!hasChrome) return;
  await chrome.storage.local.remove(["customRules"]);
};
