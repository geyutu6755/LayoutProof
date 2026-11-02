/* Node:test suite for static/i18n.js — browser-free, no dependencies. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const i18n = require("../static/i18n.js");

test("normalizeLang maps unknown codes to en and keeps zh", () => {
  assert.equal(i18n.normalizeLang("fr"), "en");
  assert.equal(i18n.normalizeLang(""), "en");
  assert.equal(i18n.normalizeLang("zh"), "zh");
  assert.ok(i18n.supported("en"));
  assert.ok(i18n.supported("zh"));
  assert.ok(!i18n.supported("ja"));
});

test("looks up English and Chinese strings with missing-key passthrough", () => {
  assert.equal(i18n.t("en", "app.title"), "LayoutProof");
  assert.ok(i18n.t("zh", "app.title"));
  assert.notEqual(i18n.t("zh", "summary.error"), i18n.t("en", "summary.error"));
  assert.equal(i18n.t("en", "missing.key"), "missing.key");
});

test("interpolates {placeholder} parameters without leaving braces", () => {
  assert.equal(i18n.t("en", "nav.slide", { number: 3 }), "Slide 3");
  const zh = i18n.t("zh", "nav.slide", { number: 3 });
  assert.ok(zh.includes("3"));
  assert.ok(!zh.includes("{"));
});

test("every English key has a Chinese counterpart", () => {
  const enKeys = Object.keys(i18n.DICT.en);
  const zhKeys = new Set(Object.keys(i18n.DICT.zh));
  assert.ok(enKeys.length >= 20);
  for (const key of enKeys) {
    assert.ok(zhKeys.has(key), `missing zh translation for ${key}`);
  }
});

test("severity and action labels exist in both languages", () => {
  for (const lang of ["en", "zh"]) {
    for (const key of [
      "summary.error", "summary.warning", "summary.info", "summary.total",
      "fix.run", "compare.before", "compare.after", "dl.fixed",
    ]) {
      assert.ok(i18n.t(lang, key), `${lang}:${key}`);
    }
  }
});
