/* i18n.js — bilingual strings (English / 中文), pure and UMD-compatible.
 * Browser: window.LPi18n.  Node tests: require('./i18n.js').
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.LPi18n = api;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const DICT = {
    en: {
      "app.title": "LayoutProof",
      "app.subtitle": "Local offline QA for AI-generated PowerPoint decks",
      "lang.toggle": "中文",
      "render.real": "Real renderer available",
      "render.static": "Static fallback — no renderer",
      "render.offline": "Core detection runs fully offline",

      "upload.drop": "Drag a .pptx deck here",
      "upload.click": "or click to choose a file",
      "upload.hint": "Only .pptx files are accepted; everything stays on this machine and no CDN or network call is used.",
      "upload.uploading": "Uploading and validating…",
      "upload.invalid": "Only .pptx decks can be opened here.",

      "deck.refresh": "Re-scan",
      "fix.run": "One-click Fix",
      "fix.running": "Repairing and re-verifying…",
      "fix.ready": "Fixed deck ready",

      "summary.error": "Errors",
      "summary.warning": "Warnings",
      "summary.info": "Info",
      "summary.total": "Total issues",
      "summary.clean": "No issues detected — deck passed the selected profile.",

      "nav.slide": "Slide {number}",
      "nav.document": "Document level",

      "preview.badge.reason": "Reason",
      "preview.empty": "Select a slide to preview issue markers.",

      "panel.slides": "Slides",
      "panel.issues": "Issues",
      "filter.all": "All",
      "filter.bySeverity": "Severity",
      "filter.search": "Filter by keyword",

      "issue.fixable": "Auto-fixable",
      "issue.manual": "Manual review",
      "issue.detail": "Detail",
      "issue.location": "Location",
      "issue.evidence": "Evidence",

      "compare.title": "Before / After fix",
      "compare.before": "Before",
      "compare.after": "After",
      "compare.removed": "Issues removed",
      "compare.applied": "Applied fixes",
      "compare.skipped": "Skipped / manual",

      "dl.fixed": "Download fixed .pptx",
      "dl.json": "Export JSON report",
      "dl.html": "Export HTML report",

      "state.scanned": "Scanned",
      "state.fixed": "Fixed",
      "state.notReady": "Run scan first",
      "state.fixNotReady": "Run fix before this download",

      "error.title": "Request failed",
      "error.unknown": "Unknown error",
      "footer": "Localhost only · static analysis without rendering engine · source file is never modified",
    },
    zh: {
      "app.title": "LayoutProof",
      "app.subtitle": "AI 生成 PPT 的本地离线质量检查工具",
      "lang.toggle": "EN",
      "render.real": "检测到真实渲染器",
      "render.static": "静态预览 —— 无渲染器",
      "render.offline": "核心检测全程离线运行",

      "upload.drop": "拖拽 .pptx 演示文稿到此处",
      "upload.click": "或点击选择文件",
      "upload.hint": "仅接受 .pptx 文件；所有数据都在本机处理，不使用 CDN、不发起网络请求。",
      "upload.uploading": "正在上传并校验文件…",
      "upload.invalid": "此处只能打开 .pptx 演示文稿。",

      "deck.refresh": "重新扫描",
      "fix.run": "一键自动修复",
      "fix.running": "正在修复并重新校验…",
      "fix.ready": "修复后的文稿已生成",

      "summary.error": "错误",
      "summary.warning": "警告",
      "summary.info": "提示",
      "summary.total": "问题总数",
      "summary.clean": "未发现问题 —— 文稿通过所选检测规则。",

      "nav.slide": "第 {number} 页",
      "nav.document": "文档级",

      "preview.badge.reason": "原因",
      "preview.empty": "选择一页查看问题定位标记。",

      "panel.slides": "幻灯片",
      "panel.issues": "问题列表",
      "filter.all": "全部",
      "filter.bySeverity": "严重级别",
      "filter.search": "按关键字筛选",

      "issue.fixable": "可自动修复",
      "issue.manual": "需人工处理",
      "issue.detail": "详情",
      "issue.location": "位置",
      "issue.evidence": "证据",

      "compare.title": "修复前 / 修复后对比",
      "compare.before": "修复前",
      "compare.after": "修复后",
      "compare.removed": "消除问题",
      "compare.applied": "已应用修复",
      "compare.skipped": "跳过 / 人工",

      "dl.fixed": "下载修复版 .pptx",
      "dl.json": "导出 JSON 报告",
      "dl.html": "导出 HTML 报告",

      "state.scanned": "已扫描",
      "state.fixed": "已修复",
      "state.notReady": "请先执行扫描",
      "state.fixNotReady": "请先执行修复再下载",

      "error.title": "请求失败",
      "error.unknown": "未知错误",
      "footer": "仅本机访问 · 未连接渲染引擎时为静态分析 · 源文件不会被修改",
    },
  };

  function normalizeLang(lang) {
    return lang === "zh" ? "zh" : "en";
  }

  function supported(lang) {
    return lang === "en" || lang === "zh";
  }

  function lookup(lang, key) {
    const norm = normalizeLang(lang);
    const chain = norm === "zh" ? ["zh", "en"] : ["en"];
    for (const code of chain) {
      if (Object.prototype.hasOwnProperty.call(DICT[code], key)) {
        return DICT[code][key];
      }
    }
    return undefined;
  }

  function t(lang, key, params) {
    let value = lookup(lang, key);
    if (value === undefined) {
      value = key;
    }
    if (params && typeof params === "object") {
      for (const name of Object.keys(params)) {
        value = value.replace(
          new RegExp("\\{" + name + "\\}", "g"),
          String(params[name])
        );
      }
    }
    return value;
  }

  return { DICT, t, normalizeLang, supported };
});
