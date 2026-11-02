/* app.js — DOM glue for the LayoutProof offline web UI.
 * Pure counting / grouping / diff logic lives in logic.js; strings in i18n.js.
 * This file talks only to the local backend API (same origin, loopback).
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const state = {
    lang: "en",
    catalog: [],
    health: null,
    sid: null,
    scan: null,
    overview: null,
    grouped: null,
    fix: null,
    afterScan: null,
    afterGrouped: null,
    beforeRender: null,
    afterRender: null,
    selectedSlide: 1,
    mode: "before",
    filters: { severity: "all", keyword: "" },
  };

  function t(key, params) {
    return LPi18n.t(state.lang, key, params);
  }

  function storeGet(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function storeSet(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* private mode */ }
  }

  async function api(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
    if (!res.ok) {
      const err = new Error(data.detail || data.error || "HTTP " + res.status);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function hideError() { $("error-banner").hidden = true; }
  function showError(message) {
    const el = $("error-banner");
    el.hidden = false;
    el.textContent = t("error.title") + ": " + message;
  }
  function setStatus(message, visible) {
    const el = $("upload-status");
    el.hidden = !visible;
    if (visible) el.textContent = message;
  }

  // ---------------------------------------------------------------- i18n
  function applyLang() {
    document.documentElement.lang = state.lang;
    $("lang-toggle").textContent = t("lang.toggle");
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    renderOverview();
    renderSlideList();
    renderStage();
    renderIssues();
    refreshDownloads();
  }

  function renderBadge() {
    const badge = $("renderer-badge");
    const renderer = state.health && state.health.renderer;
    if (!renderer) { badge.hidden = true; return; }
    badge.hidden = false;
    if (renderer.available) {
      badge.textContent = t("render.real");
      badge.className = "badge badge-real";
    } else {
      badge.textContent = t("render.static");
      badge.className = "badge badge-static";
    }
  }

  // ------------------------------------------------------------ overview
  function renderOverview() {
    const chips = $("summary-chips");
    chips.innerHTML = "";
    const summary = state.overview
      ? state.overview.summary
      : LPLogic.zeroCounts();
    const defs = [
      ["error", t("summary.error"), "chip-error"],
      ["warning", t("summary.warning"), "chip-warning"],
      ["info", t("summary.info"), "chip-info"],
      ["total", t("summary.total"), "chip-total"],
    ];
    defs.forEach(([key, label, cls]) => {
      const card = document.createElement("div");
      card.className = "chip " + cls;
      const name = document.createElement("div");
      name.className = "chip-label";
      name.textContent = label;
      const value = document.createElement("div");
      value.className = "chip-value";
      value.textContent = String(summary[key] || 0);
      card.appendChild(name);
      card.appendChild(value);
      chips.appendChild(card);
    });
  }

  function dotsHtml(bucket) {
    const parts = [];
    if (bucket.error) parts.push('<span class="dot dot-error"></span>' + bucket.error);
    if (bucket.warning) parts.push('<span class="dot dot-warning"></span>' + bucket.warning);
    if (bucket.info) parts.push('<span class="dot dot-info"></span>' + bucket.info);
    return parts.length ? parts.join(" ") : "—";
  }

  function renderSlideList() {
    const ul = $("slide-list");
    ul.innerHTML = "";
    if (!state.overview) return;
    state.overview.per_slide.forEach((bucket, idx) => {
      const li = document.createElement("li");
      li.dataset.slide = String(idx + 1);
      if (state.selectedSlide === idx + 1) li.classList.add("active");
      const label = document.createElement("span");
      label.textContent = t("nav.slide", { number: idx + 1 });
      const counts = document.createElement("span");
      counts.className = "slide-counts";
      counts.innerHTML = dotsHtml(bucket);
      li.appendChild(label);
      li.appendChild(counts);
      li.addEventListener("click", () => selectSlide(idx + 1));
      ul.appendChild(li);
    });
    const doc = state.overview.document;
    if (doc.total > 0) {
      const li = document.createElement("li");
      li.dataset.slide = "0";
      if (state.selectedSlide === 0) li.classList.add("active");
      const label = document.createElement("span");
      label.textContent = t("nav.document");
      const counts = document.createElement("span");
      counts.className = "slide-counts";
      counts.innerHTML = dotsHtml(doc);
      li.appendChild(label);
      li.appendChild(counts);
      li.addEventListener("click", () => selectSlide(0));
      ul.appendChild(li);
    }
  }

  function selectSlide(number) {
    state.selectedSlide = number;
    document.querySelectorAll("#slide-list li").forEach((li) => {
      li.classList.toggle("active", Number(li.dataset.slide) === number);
    });
    renderStage();
    renderIssues();
  }

  function currentGroup() {
    if (state.mode === "after" && state.afterGrouped) return state.afterGrouped;
    return state.grouped || { slides: [], document: { issues: [] } };
  }

  function issuesForSlide(number) {
    const group = currentGroup();
    if (number === 0) return group.document.issues || [];
    const bucket = group.slides[number - 1];
    return bucket ? bucket.issues : [];
  }

  // --------------------------------------------------------------- stage
  function currentScan() {
    return state.mode === "after" && state.afterScan ? state.afterScan : state.scan;
  }

  function renderBanner() {
    const banner = $("render-banner");
    const manifest = state.mode === "after" ? state.afterRender : state.beforeRender;
    if (!manifest) { banner.hidden = true; return; }
    banner.hidden = false;
    if (manifest.rendered) {
      banner.textContent = t("render.real");
      banner.style.background = "var(--info-soft)";
      banner.style.color = "var(--info)";
    } else {
      banner.textContent = t("render.static") +
        (manifest.reason ? " — " + manifest.reason : "");
      banner.style.background = "var(--warning-soft)";
      banner.style.color = "var(--warning)";
    }
  }

  function renderMarkers(issues) {
    const layer = $("marker-layer");
    layer.innerHTML = "";
    issues.forEach((issue, idx) => {
      const style = LPLogic.markerStyle(issue.normalized_location);
      if (!style) return;
      const marker = document.createElement("div");
      marker.className = "marker " + LPLogic.severityClass(issue.severity);
      Object.assign(marker.style, style);
      const num = document.createElement("span");
      num.className = "marker-num";
      num.textContent = String(idx + 1);
      marker.appendChild(num);
      marker.title = issue.rule_id + (issue.detail ? " — " + issue.detail : "");
      layer.appendChild(marker);
    });
  }

  function renderStage() {
    const manifest = state.mode === "after" ? state.afterRender : state.beforeRender;
    const img = $("slide-image");
    const placeholder = $("slide-placeholder");
    const frame = $("slide-frame");
    const aspect = LPLogic.slideAspect(currentScan());
    if (aspect) frame.style.aspectRatio = aspect.css;

    const canShowImage = manifest && manifest.rendered && state.selectedSlide > 0;
    if (canShowImage) {
      img.hidden = false;
      img.src = "/api/image/" + state.sid + "/" + state.mode +
        "/" + state.selectedSlide + ".png";
      placeholder.hidden = true;
    } else {
      img.hidden = true;
      img.removeAttribute("src");
      placeholder.hidden = false;
      placeholder.textContent = t("preview.empty");
    }
    renderMarkers(issuesForSlide(state.selectedSlide));
    renderBanner();

    const total = state.scan ? state.scan.slide_count : 0;
    $("slide-nav-label").textContent = state.selectedSlide > 0
      ? t("nav.slide", { number: state.selectedSlide }) + " / " + total
      : t("nav.document");
  }

  // ---------------------------------------------------------------- issues
  function renderIssues() {
    const list = $("issue-list");
    list.innerHTML = "";
    const filtered = LPLogic.filterIssues(issuesForSlide(state.selectedSlide), state.filters);
    if (!filtered.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = t("summary.clean");
      list.appendChild(li);
      return;
    }
    filtered.forEach((issue) => {
      const rule = LPLogic.findRule(state.catalog, issue.rule_id);
      const card = document.createElement("li");
      card.className = "issue-card " + LPLogic.severityClass(issue.severity);

      const title = document.createElement("div");
      title.className = "issue-title";
      title.textContent = rule
        ? (state.lang === "zh" ? rule.title_zh : rule.title_en)
        : issue.rule_id;
      const tag = document.createElement("span");
      tag.className = "issue-tag " + (issue.fixable ? "tag-fixable" : "tag-manual");
      tag.textContent = issue.fixable ? t("issue.fixable") : t("issue.manual");
      title.appendChild(tag);
      card.appendChild(title);

      const meta = document.createElement("div");
      meta.className = "issue-meta";
      const where = issue.slide_number
        ? t("nav.slide", { number: issue.slide_number })
        : t("nav.document");
      meta.textContent = where + " · " + issue.rule_id +
        (issue.shape_name ? " · " + issue.shape_name : "");
      card.appendChild(meta);

      if (issue.detail) {
        const detail = document.createElement("div");
        detail.className = "issue-meta";
        detail.textContent = t("issue.detail") + ": " + issue.detail;
        card.appendChild(detail);
      }
      list.appendChild(card);
    });
  }

  // ---------------------------------------------------------------- compare
  function renderCompare(fixPayload) {
    const section = $("fix-compare");
    const before = fixPayload.before_overview && fixPayload.before_overview.summary;
    const after = fixPayload.after_overview && fixPayload.after_overview.summary;
    if (!before || !after) { section.hidden = true; return; }
    section.hidden = false;
    const diff = LPLogic.buildFixDiff(before, after);
    const cards = $("compare-cards");
    cards.innerHTML = "";
    const makeCard = (label, summary, delta) => {
      const card = document.createElement("div");
      card.className = "compare-card";
      const head = document.createElement("h4");
      head.textContent = label;
      card.appendChild(head);
      const body = document.createElement("div");
      body.textContent = t("summary.total") + ": " + summary.total +
        " | " + t("summary.error") + ": " + summary.error +
        " / " + t("summary.warning") + ": " + summary.warning +
        " / " + t("summary.info") + ": " + summary.info;
      card.appendChild(body);
      if (delta !== undefined) {
        const deltaEl = document.createElement("div");
        deltaEl.className = delta < 0 ? "delta-good" : (delta > 0 ? "delta-bad" : "muted");
        deltaEl.textContent = (delta < 0 ? "−" + Math.abs(delta) : String(delta));
        card.appendChild(deltaEl);
      }
      cards.appendChild(card);
    };
    makeCard(t("compare.before"), before, undefined);
    makeCard(t("compare.after"), after, diff.removed);
    const note = $("fix-notes");
    note.textContent = t("compare.removed") + ": " + diff.removed +
      " · " + t("compare.applied") + ": " + fixPayload.fix.applied.length +
      " · " + t("compare.skipped") + ": " + fixPayload.fix.skipped.length +
      (fixPayload.fix.note ? " · " + fixPayload.fix.note : "");
  }

  function refreshDownloads() {
    $("dl-json").hidden = !state.scan;
    $("dl-html").hidden = !state.scan;
    $("dl-fixed").hidden = !(state.fix && state.fix.created);
    if (!state.sid) return;
    $("dl-json").href = "/api/report/json/" + state.sid;
    $("dl-html").href = "/api/report/html/" + state.sid + "?lang=" + state.lang;
    $("dl-fixed").href = "/api/download/fixed/" + state.sid;
  }

  // ---------------------------------------------------------------- flows
  async function ensureRender(stage) {
    try {
      const data = await api("GET", "/api/render/" + state.sid + "/" + stage);
      if (stage === "before") state.beforeRender = data.render;
      else state.afterRender = data.render;
      renderBanner();
      renderStage();
    } catch (e) {
      /* optional renderer: static geometry preview remains available */
    }
  }

  async function runScan() {
    hideError();
    try {
      const data = await api("POST", "/api/scan", {
        session_id: state.sid,
        profile: "core",
      });
      state.scan = data.scan;
      state.overview = data.overview;
      state.grouped = LPLogic.groupIssuesBySlide(
        data.scan.issues, data.scan.slide_count);
      state.selectedSlide = Math.min(
        Math.max(1, state.selectedSlide || 1),
        Math.max(1, data.scan.slide_count));
      if (data.scan.status === "error") {
        showError(data.scan.error || "scan error");
      }
      renderOverview();
      renderSlideList();
      renderStage();
      renderIssues();
      refreshDownloads();
      await ensureRender("before");
    } catch (e) { showError(e.message); }
  }

  async function runFix() {
    hideError();
    $("btn-fix").disabled = true;
    try {
      const data = await api("POST", "/api/fix", {
        session_id: state.sid,
        profile: "core",
      });
      state.fix = data.fix;
      if (data.after_scan) {
        state.afterScan = data.after_scan;
        state.afterGrouped = LPLogic.groupIssuesBySlide(
          data.after_scan.issues, data.after_scan.slide_count);
      }
      state.mode = "after";
      $("mode-after").classList.add("active");
      $("mode-before").classList.remove("active");
      renderCompare(data);
      refreshDownloads();
      await ensureRender("after");
      renderStage();
      renderSlideList();
      renderIssues();
    } catch (e) { showError(e.message); }
    $("btn-fix").disabled = false;
  }

  async function handleFile(file) {
    hideError();
    if (!file) return;
    const check = LPLogic.validateDeckFileName(file.name);
    if (!check.valid) {
      showError(t("upload.invalid") + " (" + check.reason + ")");
      return;
    }
    setStatus(t("upload.uploading"), true);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "HTTP " + res.status);
      state.sid = data.session_id;
      state.mode = "before";
      $("mode-before").classList.add("active");
      $("mode-after").classList.remove("active");
      $("deck-panel").hidden = false;
      $("deck-name").textContent = data.file_name;
      $("deck-meta").textContent = LPLogic.formatBytes(data.size_bytes);
      await runScan();
    } catch (e) { showError(e.message); }
    setStatus("", false);
  }

  function setMode(mode) {
    state.mode = mode;
    $("mode-before").classList.toggle("active", mode === "before");
    $("mode-after").classList.toggle("active", mode === "after");
    renderBanner();
    renderStage();
    renderIssues();
  }

  function bindEvents() {
    const dropzone = $("dropzone");
    const input = $("file-input");
    dropzone.addEventListener("click", () => input.click());
    dropzone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      handleFile(e.dataTransfer.files && e.dataTransfer.files[0]);
    });
    input.addEventListener("change", () => handleFile(input.files && input.files[0]));

    $("btn-scan").addEventListener("click", runScan);
    $("btn-fix").addEventListener("click", runFix);
    $("mode-before").addEventListener("click", () => setMode("before"));
    $("mode-after").addEventListener("click", () => setMode("after"));

    $("filter-severity").addEventListener("change", (e) => {
      state.filters.severity = e.target.value;
      renderIssues();
    });
    $("filter-keyword").addEventListener("input", (e) => {
      state.filters.keyword = e.target.value;
      renderIssues();
    });
    $("prev-slide").addEventListener("click", () => {
      const max = state.scan ? state.scan.slide_count : 1;
      selectSlide(((state.selectedSlide - 2 + max) % max) + 1);
    });
    $("next-slide").addEventListener("click", () => {
      const max = state.scan ? state.scan.slide_count : 1;
      selectSlide((state.selectedSlide % max) + 1);
    });
    $("lang-toggle").addEventListener("click", () => {
      state.lang = state.lang === "zh" ? "en" : "zh";
      storeSet("lp-lang", state.lang);
      applyLang();
    });
  }

  async function boot() {
    state.lang = LPi18n.normalizeLang(storeGet("lp-lang") || "en");
    bindEvents();
    applyLang();
    try {
      state.health = await api("GET", "/api/health");
      renderBadge();
    } catch (e) { /* badge hidden when server unreachable */ }
    try {
      const meta = await api("GET", "/api/meta");
      state.catalog = meta.rules;
    } catch (e) { /* rules optional; rule ids still shown */ }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
