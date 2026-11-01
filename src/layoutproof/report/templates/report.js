(function () {
  "use strict";

  var body = document.body;
  var dataEl = document.getElementById("issues-data");
  var issues = dataEl ? JSON.parse(dataEl.textContent) : [];

  var cards = Array.prototype.slice.call(document.querySelectorAll(".issue"));
  var fileSel = document.getElementById("filter-file");
  var slideSel = document.getElementById("filter-slide");
  var searchEl = document.getElementById("filter-search");
  var stage = document.getElementById("stage");
  var stageLabel = document.getElementById("stage-label");
  var langBtn = document.getElementById("lang-toggle");

  var LANG = body.classList.contains("lang-zh") ? "zh" : "en";

  // ---- populate file / slide dropdowns -------------------------------------
  var filesSeen = {};
  var slidesSeen = {};
  issues.forEach(function (it) {
    if (it.file_name && !filesSeen[it.file_name]) {
      filesSeen[it.file_name] = true;
      var fo = document.createElement("option");
      fo.value = it.file_name;
      fo.textContent = it.file_name;
      fileSel.appendChild(fo);
    }
    if (it.slide_number && it.slide_number > 0 && !slidesSeen[it.slide_number]) {
      slidesSeen[it.slide_number] = true;
      var so = document.createElement("option");
      so.value = String(it.slide_number);
      so.textContent = (LANG === "zh" ? "幻灯片 " : "Slide ") + it.slide_number;
      slideSel.appendChild(so);
    }
  });

  // ---- filtering -----------------------------------------------------------
  function activeSeverities() {
    var out = {};
    document.querySelectorAll("[data-sev]").forEach(function (cb) {
      out[cb.getAttribute("data-sev")] = cb.checked;
    });
    return out;
  }

  function applyFilters() {
    var f = fileSel.value;
    var s = slideSel.value;
    var sevs = activeSeverities();
    var q = (searchEl.value || "").toLowerCase();
    cards.forEach(function (card) {
      var ok = true;
      if (f !== "all" && card.getAttribute("data-file") !== f) ok = false;
      if (s !== "all" && card.getAttribute("data-slide") !== s) ok = false;
      if (!sevs[card.getAttribute("data-severity")]) ok = false;
      if (q && card.textContent.toLowerCase().indexOf(q) === -1) ok = false;
      card.classList.toggle("hidden", !ok);
    });
  }

  fileSel.addEventListener("change", applyFilters);
  slideSel.addEventListener("change", applyFilters);
  searchEl.addEventListener("input", applyFilters);
  document.querySelectorAll("[data-sev]").forEach(function (cb) {
    cb.addEventListener("change", applyFilters);
  });

  // ---- location preview -----------------------------------------------------
  function clearStage() {
    Array.prototype.slice.call(stage.querySelectorAll(".stage-box")).forEach(function (b) {
      b.parentNode.removeChild(b);
    });
    var ph = stage.querySelector(".stage-placeholder");
    if (ph) ph.style.display = "none";
  }

  function locate(index) {
    var issue = issues[index];
    if (!issue) return;
    clearStage();
    if (issue.slide_number && issue.slide_number > 0) {
      stageLabel.textContent =
        (LANG === "zh" ? "幻灯片 " : "Slide ") + issue.slide_number;
    } else {
      stageLabel.textContent = LANG === "zh" ? "文档级" : "Document level";
    }

    var nl = issue.normalized_location;
    if (!nl) {
      var msg = document.createElement("div");
      msg.className = "stage-placeholder muted";
      msg.textContent =
        LANG === "zh" ? "该问题无可视化位置数据。" : "No positional data for this issue.";
      stage.appendChild(msg);
      return;
    }

    // draw all issues on the same slide for context
    issues.forEach(function (other, i) {
      if (other.slide_number !== issue.slide_number) return;
      if (!other.normalized_location) return;
      var r = other.normalized_location;
      var box = document.createElement("div");
      box.className = "stage-box sev-" + other.severity + (i === index ? " active" : "");
      box.style.left = (r.x * 100) + "%";
      box.style.top = (r.y * 100) + "%";
      box.style.width = (r.width * 100) + "%";
      box.style.height = (r.height * 100) + "%";
      stage.appendChild(box);
    });
  }

  cards.forEach(function (card) {
    var idx = Number(card.getAttribute("data-index"));
    var btn = card.querySelector("[data-locate]");
    if (btn) btn.addEventListener("click", function (e) {
      e.stopPropagation();
      locate(idx);
    });
    card.addEventListener("click", function () { locate(idx); });
  });

  // ---- language toggle -----------------------------------------------------
  function setLang(lang) {
    LANG = lang;
    body.classList.toggle("lang-en", lang === "en");
    body.classList.toggle("lang-zh", lang === "zh");
    body.setAttribute("class", body.classList.toString());
    langBtn.textContent = lang === "en" ? "中文" : "EN";
    var allFile = document.getElementById("opt-all-file");
    var allSlide = document.getElementById("opt-all-slide");
    var allLabel = lang === "zh" ? "全部" : "All";
    if (allFile) allFile.textContent = allLabel;
    if (allSlide) allSlide.textContent = allLabel;
    // rebuild slide labels
    Array.prototype.slice.call(slideSel.options).forEach(function (o) {
      if (o.value !== "all") {
        o.textContent = (lang === "zh" ? "幻灯片 " : "Slide ") + o.value;
      }
    });
  }
  langBtn.addEventListener("click", function () {
    setLang(LANG === "en" ? "zh" : "en");
  });
  setLang(LANG);
})();
