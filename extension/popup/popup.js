// popup：读写 chrome.storage.sync.settings；content script 监听 storage 变化实时生效。
(function () {
  const DEFAULTS = {
    enabled: true,
    onlyHigh: false,
    sections: { pii: true, credentials: true, topics: true, custom: true },
    customKeywords: [],
  };

  const $ = (id) => document.getElementById(id);

  function load() {
    chrome.storage.sync.get(["settings"], (got) => {
      const s = Object.assign({}, DEFAULTS, got.settings || {});
      $("enabled").checked = s.enabled !== false;
      $("onlyHigh").checked = !!s.onlyHigh;
      document.querySelectorAll(".sec").forEach((el) => {
        el.checked = s.sections[el.dataset.sec] !== false;
      });
    });
  }

  function save() {
    const settings = {
      enabled: $("enabled").checked,
      onlyHigh: $("onlyHigh").checked,
      sections: {},
      customKeywords: DEFAULTS.customKeywords,
    };
    document.querySelectorAll(".sec").forEach((el) => {
      settings.sections[el.dataset.sec] = el.checked;
    });
    chrome.storage.sync.get(["settings"], (got) => {
      const prev = Object.assign({}, DEFAULTS, got.settings || {});
      settings.customKeywords = prev.customKeywords || [];
      chrome.storage.sync.set({ settings });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    load();
    document.querySelectorAll("input").forEach((el) => el.addEventListener("change", save));
    $("openOptions").addEventListener("click", (e) => {
      e.preventDefault();
      chrome.runtime.openOptionsPage();
    });
  });
})();
