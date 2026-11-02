/* Node:test suite for static/logic.js — pure UI logic, DOM-free. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const L = require("../static/logic.js");

test("severityCounts buckets three tiers and a total", () => {
  const counts = L.severityCounts([
    { severity: "error" },
    { severity: "warning" },
    { severity: "warning" },
    { severity: "info" },
  ]);
  assert.deepEqual(
    { error: counts.error, warning: counts.warning, info: counts.info, total: counts.total },
    { error: 1, warning: 2, info: 1, total: 4 }
  );
  assert.equal(L.severityCounts(null).total, 0);
  assert.equal(L.severityCounts(undefined).total, 0);
});

test("groupIssuesBySlide separates per-slide and document-level buckets", () => {
  const issues = [
    { slide_number: 1, severity: "error" },
    { slide_number: 1, severity: "warning" },
    { slide_number: 2, severity: "info" },
    { slide_number: 0, severity: "warning" },
  ];
  const group = L.groupIssuesBySlide(issues, 2);
  assert.equal(group.slides[0].counts.error, 1);
  assert.equal(group.slides[0].counts.warning, 1);
  assert.equal(group.slides[1].counts.info, 1);
  assert.equal(group.document.counts.warning, 1);
  assert.equal(group.document.counts.total, 1);
});

test("buildFixDiff reports removed, added and improvement trend", () => {
  const improved = L.buildFixDiff(
    { error: 1, warning: 2, info: 0, total: 3 },
    { error: 0, warning: 1, info: 0, total: 1 }
  );
  assert.equal(improved.removed, 2);
  assert.equal(improved.added, 0);
  assert.equal(improved.improved, true);
  assert.equal(improved.neutral, false);
  assert.equal(improved.bySeverity.error.delta, -1);

  const regressed = L.buildFixDiff({ total: 1 }, { total: 2 });
  assert.equal(regressed.added, 1);
  assert.equal(regressed.improved, false);

  const neutral = L.buildFixDiff({ total: 2 }, { total: 2 });
  assert.equal(neutral.neutral, true);
});

test("validateDeckFileName accepts real decks and rejects attack shapes", () => {
  assert.equal(L.validateDeckFileName("deck.pptx").valid, true);
  assert.equal(L.validateDeckFileName("UPPER.PPTX").valid, true);

  const rejected = [
    "../../../evil.exe",
    "notes.txt",
    "",
    "   ",
    ".pptx",
    "dir/sub.pptx",
    "name\x00.pptx",
    "a".repeat(260) + ".pptx",
  ];
  for (const name of rejected) {
    assert.equal(L.validateDeckFileName(name).valid, false, name);
  }
});

test("markerStyle converts normalized fractions to clamped CSS percentages", () => {
  const marker = L.markerStyle({ x: 0.1, y: 0.2, width: 0.3, height: 0.4 });
  assert.equal(marker.left, "10.000%");
  assert.equal(marker.top, "20.000%");
  assert.equal(marker.width, "30.000%");
  assert.equal(marker.height, "40.000%");

  assert.equal(L.markerStyle(null), null);
  assert.equal(L.markerStyle(undefined), null);
  // Off-slide boxes may exceed 1; width below zero collapses to null.
  assert.equal(L.markerStyle({ x: 1.5, y: 0, width: 0.2, height: 0.2 }).left, "100.000%");
  assert.equal(L.markerStyle({ x: 0, y: 0, width: -1, height: 0.2 }), null);
});

test("filterIssues applies severity, slide and keyword filters", () => {
  const issues = [
    { rule_id: "font_too_small", severity: "error", slide_number: 1, detail: "tiny font", shape_name: "A" },
    { rule_id: "low_contrast", severity: "warning", slide_number: 1, detail: "contrast ratio", shape_name: "B" },
    { rule_id: "offslide_object", severity: "error", slide_number: 2, detail: "outside canvas", shape_name: "C" },
  ];
  assert.equal(L.filterIssues(issues, { severity: "error" }).length, 2);
  assert.equal(L.filterIssues(issues, { severity: "all" }).length, 3);
  assert.equal(L.filterIssues(issues, { slideNumber: 2 }).length, 1);
  assert.equal(L.filterIssues(issues, { keyword: "contrast" }).length, 1);
  assert.equal(L.filterIssues(issues, { keyword: "MISSINGWORD" }).length, 0);
});

test("severityClass maps known tiers and falls back safely", () => {
  assert.equal(L.severityClass("error"), "sev-error");
  assert.equal(L.severityClass("warning"), "sev-warning");
  assert.equal(L.severityClass("info"), "sev-info");
  assert.equal(L.severityClass("weird"), "sev-unknown");
});

test("findRule matches catalog entries by id", () => {
  const catalog = [{ id: "font_too_small" }, { id: "offslide_object" }];
  assert.equal(L.findRule(catalog, "offslide_object").id, "offslide_object");
  assert.equal(L.findRule(catalog, "missing"), null);
});

test("slideAspect derives CSS ratio from EMU dimensions", () => {
  const aspect = L.slideAspect({ slide_width: 9144000, slide_height: 6858000 });
  assert.ok(aspect.ratio > 0);
  assert.equal(aspect.css, "9144000 / 6858000");
  assert.equal(L.slideAspect(null), null);
  assert.equal(L.slideAspect({ slide_width: 0, slide_height: 0 }), null);
});

test("formatBytes renders human-friendly sizes", () => {
  assert.equal(L.formatBytes(512), "512 B");
  assert.ok(L.formatBytes(4096).includes("KiB"));
  assert.ok(L.formatBytes(4 * 1024 * 1024).includes("MiB"));
  assert.equal(L.formatBytes(undefined), "—");
});

test("shouldShowStaticBadge is true unless a rendered manifest exists", () => {
  assert.equal(L.shouldShowStaticBadge(null), true);
  assert.equal(L.shouldShowStaticBadge({ rendered: false }), true);
  assert.equal(L.shouldShowStaticBadge({ rendered: true }), false);
});
