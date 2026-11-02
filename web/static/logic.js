/* logic.js — pure client-side interactive logic for the LayoutProof UI.
 * No DOM access here so the Node test suite can exercise the rules directly.
 * Browser: window.LPLogic.  Node: require('./logic.js').
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.LPLogic = api;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const SEVERITIES = ["error", "warning", "info"];

  function zeroCounts() {
    return { error: 0, warning: 0, info: 0, total: 0 };
  }

  function severityCounts(issues) {
    const counts = zeroCounts();
    if (!Array.isArray(issues)) {
      return counts;
    }
    for (const issue of issues) {
      const sev = issue && issue.severity;
      if (sev === "error" || sev === "warning" || sev === "info") {
        counts[sev] += 1;
      } else {
        counts.warning += 0; // unknown severity stays out of the three-tier sum
      }
    }
    counts.total = counts.error + counts.warning + counts.info;
    return counts;
  }

  function groupIssuesBySlide(issues, slideCount) {
    const slides = [];
    for (let i = 0; i < slideCount; i += 1) {
      slides.push({ slideNumber: i + 1, issues: [], counts: zeroCounts() });
    }
    const documentBucket = { slideNumber: 0, issues: [], counts: zeroCounts() };
    if (!Array.isArray(issues)) {
      return { slides, document: documentBucket };
    }
    for (const issue of issues) {
      const bucket =
        !issue.slide_number || issue.slide_number <= 0
          ? documentBucket
          : slides[issue.slide_number - 1];
      if (bucket) {
        bucket.issues.push(issue);
        if (issue.severity && bucket.counts[issue.severity] !== undefined) {
          bucket.counts[issue.severity] += 1;
        }
      }
    }
    for (const bucket of slides) {
      bucket.counts.total =
        bucket.counts.error + bucket.counts.warning + bucket.counts.info;
    }
    documentBucket.counts.total =
      documentBucket.counts.error +
      documentBucket.counts.warning +
      documentBucket.counts.info;
    return { slides, document: documentBucket };
  }

  function buildFixDiff(beforeSummary, afterSummary) {
    const before = Object.assign(zeroCounts(), beforeSummary || {});
    const after = Object.assign(zeroCounts(), afterSummary || {});
    const bySeverity = {};
    for (const sev of SEVERITIES) {
      bySeverity[sev] = { before: before[sev] || 0, after: after[sev] || 0 };
      bySeverity[sev].delta = bySeverity[sev].after - bySeverity[sev].before;
    }
    const removed = Math.max(0, before.total - after.total);
    const added = Math.max(0, after.total - before.total);
    return {
      before,
      after,
      bySeverity,
      removed,
      added,
      improved: after.total < before.total,
      neutral: after.total === before.total,
    };
  }

  function validateDeckFileName(name) {
    if (typeof name !== "string" || name.length === 0) {
      return { valid: false, reason: "empty_name" };
    }
    const cleaned = name.trim();
    if (!cleaned) {
      return { valid: false, reason: "empty_name" };
    }
    if (cleaned.length > 255) {
      return { valid: false, reason: "name_too_long" };
    }
    if (/[\\\x00-\x1f]/.test(cleaned)) {
      return { valid: false, reason: "illegal_characters" };
    }
    if (cleaned.includes("/")) {
      return { valid: false, reason: "path_separator" };
    }
    if (!cleaned.toLowerCase().endsWith(".pptx")) {
      return { valid: false, reason: "wrong_extension" };
    }
    const stem = cleaned.slice(0, -5);
    if (!stem.trim()) {
      return { valid: false, reason: "empty_stem" };
    }
    return { valid: true, reason: null };
  }

  function clamp01(value) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
      return 0;
    }
    if (value > 1) {
      return 1;
    }
    return value;
  }

  function markerStyle(normalizedLocation) {
    if (!normalizedLocation) {
      return null;
    }
    const x = clamp01(normalizedLocation.x);
    const y = clamp01(normalizedLocation.y);
    const w = clamp01(normalizedLocation.width);
    const h = clamp01(normalizedLocation.height);
    if (w <= 0 || h <= 0) {
      return null;
    }
    return {
      left: (x * 100).toFixed(3) + "%",
      top: (y * 100).toFixed(3) + "%",
      width: (w * 100).toFixed(3) + "%",
      height: (h * 100).toFixed(3) + "%",
    };
  }

  function severityClass(severity) {
    if (severity === "error") return "sev-error";
    if (severity === "warning") return "sev-warning";
    if (severity === "info") return "sev-info";
    return "sev-unknown";
  }

  function findRule(catalog, ruleId) {
    if (!Array.isArray(catalog)) return null;
    return catalog.find((rule) => rule && rule.id === ruleId) || null;
  }

  function filterIssues(issues, filters) {
    const opts = filters || {};
    if (!Array.isArray(issues)) return [];
    const keyword = (opts.keyword || "").trim().toLowerCase();
    return issues.filter((issue) => {
      if (opts.severity && opts.severity !== "all" && issue.severity !== opts.severity) {
        return false;
      }
      if (
        Number.isInteger(opts.slideNumber) &&
        opts.slideNumber >= 0 &&
        issue.slide_number !== opts.slideNumber
      ) {
        return false;
      }
      if (keyword) {
        const haystack = [
          issue.rule_id,
          issue.detail,
          issue.shape_name,
          issue.severity,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(keyword)) {
          return false;
        }
      }
      return true;
    });
  }

  function slideAspect(scan) {
    if (!scan) return null;
    const w = Number(scan.slide_width);
    const h = Number(scan.slide_height);
    if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) {
      return null;
    }
    return { width: w, height: h, ratio: w / h, css: w + " / " + h };
  }

  function formatBytes(bytes) {
    const n = Number(bytes);
    if (!Number.isFinite(n) || n < 0) return "—";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KiB";
    return (n / (1024 * 1024)).toFixed(1) + " MiB";
  }

  function shouldShowStaticBadge(renderManifest) {
    if (!renderManifest) return true;
    return renderManifest.rendered !== true;
  }

  return {
    SEVERITIES,
    zeroCounts,
    severityCounts,
    groupIssuesBySlide,
    buildFixDiff,
    validateDeckFileName,
    markerStyle,
    severityClass,
    findRule,
    filterIssues,
    slideAspect,
    formatBytes,
    shouldShowStaticBadge,
  };
});
