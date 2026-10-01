// options：自定义关键词（storage.sync）+ 规则导入导出（storage.local.customRules）。
(function () {
  const $ = (id) => document.getElementById(id);
  const SECTION_KEYS = ["pii", "credentials", "topics"];

  function loadKeywords() {
    chrome.storage.sync.get(["settings"], (got) => {
      const kws = (got.settings && got.settings.customKeywords) || [];
      $("keywords").value = kws.join("\n");
    });
  }

  function say(msg) {
    $("status").textContent = msg;
    setTimeout(() => ($("status").textContent = ""), 2500);
  }

  function validateRules(json) {
    if (!json || typeof json !== "object") return "根节点必须是对象";
    for (const sec of SECTION_KEYS) {
      if (!Array.isArray(json[sec])) return "缺少数组字段: " + sec;
      for (const r of json[sec]) {
        if (!r.id || !r.label || !r.pattern) return sec + " 中存在缺 id/label/pattern 的规则";
        try {
          new RegExp(r.pattern, (r.flags || "").includes("i") ? "gi" : "g");
        } catch (e) {
          return "规则 " + r.id + " 正则无法编译: " + e.message;
        }
      }
    }
    return null;
  }

  document.addEventListener("DOMContentLoaded", () => {
    loadKeywords();

    $("saveKw").addEventListener("click", () => {
      const words = $("keywords").value.split("\n").map((s) => s.trim()).filter(Boolean);
      chrome.storage.sync.get(["settings"], (got) => {
        const s = got.settings || {};
        s.customKeywords = words;
        chrome.storage.sync.set({ settings: s }, () => say("已保存"));
      });
    });

    $("exportBtn").addEventListener("click", async () => {
      let rules;
      try {
        const local = await chrome.storage.local.get(["customRules"]);
        if (local.customRules) {
          rules = local.customRules;
        } else {
          const res = await fetch(chrome.runtime.getURL("rules/sensitive-rules.json"));
          rules = await res.json();
        }
      } catch (e) {
        say("导出失败: " + e.message);
        return;
      }
      const blob = new Blob([JSON.stringify(rules, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "x-risk-audit-rules.json";
      a.click();
      URL.revokeObjectURL(a.href);
      say("已导出");
    });

    $("importBtn").addEventListener("click", () => $("importFile").click());
    $("importFile").addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        let json;
        try {
          json = JSON.parse(reader.result);
        } catch (err) {
          say("JSON 解析失败");
          return;
        }
        const err = validateRules(json);
        if (err) {
          say("校验失败: " + err);
          return;
        }
        chrome.storage.local.set({ customRules: json }, () => say("已导入，刷新 x.com 页面生效"));
      };
      reader.readAsText(file);
      e.target.value = "";
    });

    $("resetBtn").addEventListener("click", () => {
      chrome.storage.local.remove(["customRules"], () => say("已恢复内置规则"));
    });
  });
})();
