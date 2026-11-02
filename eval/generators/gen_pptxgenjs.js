/* PptxGenJS authored eval corpus (local, offline).
 *
 * Emits one independent .pptx per scenario into ../corpus/pptxgenjs and a
 * machine-readable ground-truth manifest part ../corpus/pptxgenjs/manifest_part.json.
 * Run with the Node v22 shipped with this environment:
 *   node gen_pptxgenjs.js [outDir]
 *
 * GT conventions mirror eval/generators/schema.py: positive = planted defect;
 * negative = deliberate clean sample; anything uncertain is omitted.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const PptxGenJS = require("../nodeenv/node_modules/pptxgenjs");

const OUT_DIR = process.argv[2] || path.join(__dirname, "..", "corpus", "pptxgenjs");
fs.mkdirSync(OUT_DIR, { recursive: true });

const SEV = {
  offslide_object: "error", font_too_small: "error", text_overflow: "warning",
  unfinished_placeholder: "warning", media_broken: "error", broken_reference: "error",
  structure_anomaly: "error", object_overlap: "warning", low_contrast: "warning",
  blank_slide: "warning", missing_alt_text: "info", cjk_typography: "warning",
};
const CORE = new Set(["offslide_object", "font_too_small", "text_overflow",
  "unfinished_placeholder", "media_broken", "broken_reference", "structure_anomaly"]);
const scope = (r) => (CORE.has(r) ? "both" : "full");

function J(rule, expect, basis, note = "", extra = {}) {
  return {
    rule_id: rule, expect, profiles: extra.profiles || scope(rule),
    expected_severity: SEV[rule], basis, note, expected_count: extra.count || null,
  };
}

function rec(contentId, file, lang, aspect, scenario, description, judgements, extra = {}) {
  return {
    content_id: contentId, file, source: "pptxgenjs", language: lang, aspect,
    scenario, description, parent: null, expected_status: "ok", build_note: "",
    judgements, ...extra,
  };
}

// ---------------------------------------------------------------------------
// Minimal valid RGB PNG data URI (8x8), no external image dependency
// ---------------------------------------------------------------------------
const crcTable = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? (0xEDB88320 ^ (c >>> 1)) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = ~0;
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (~c) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const typeBuf = Buffer.from(type, "ascii");
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])));
  return Buffer.concat([len, typeBuf, data, crc]);
}
function pngUri([r, g, b], size = 8) {
  const sig = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 2;
  const raw = Buffer.alloc(size * (1 + size * 3));
  for (let y = 0; y < size; y++) {
    raw[y * (1 + size * 3)] = 0;
    for (let x = 0; x < size; x++) {
      const o = y * (1 + size * 3) + 1 + x * 3;
      raw[o] = r; raw[o + 1] = g; raw[o + 2] = b;
    }
  }
  const idat = zlib.deflateSync(raw);
  const png = Buffer.concat([sig, chunk("IHDR", ihdr), chunk("IDAT", idat), chunk("IEND", Buffer.alloc(0))]);
  return "data:image/png;base64," + png.toString("base64");
}

// ---------------------------------------------------------------------------
// small deck helpers (units: inches)
// ---------------------------------------------------------------------------
function deck(aspect) {
  const p = new PptxGenJS();
  if (aspect === "4:3") {
    p.defineLayout({ name: "Q43", width: 10, height: 7.5 });
  } else {
    p.defineLayout({ name: "W169", width: 13.333, height: 7.5 });
  }
  p.layout = aspect === "4:3" ? "Q43" : "W169";
  return p;
}
function text(s, str, o = {}) {
  s.addText(str, Object.assign(
    { x: 0.55, y: 0.4, w: 12.1, h: 0.7, fontSize: 22, color: "222222", align: "left", wrap: true },
    o));
}
function rect(s, o, fill = "DDE6F0", line = "99AABB") {
  s.addShape("rect", Object.assign(
    { fill: { color: fill }, line: { color: line } }, o));
}
function table(s, rows, o = {}) {
  s.addTable(rows, Object.assign(
    { x: 0.55, y: 2.3, w: 5.6, colW: [1.8, 1.8, 1.8], fontSize: 14, border: { pt: 0.5, color: "BBBBBB" } }, o));
}

// ---------------------------------------------------------------------------
// scenarios: [contentId, fileStem, lang, aspect, scenario, description,
//             builder(p), recordExtra]
// ---------------------------------------------------------------------------
const scenarios = [];
async function save(p, file) {
  await p.writeFile({ fileName: path.join(OUT_DIR, file) });
}

scenarios.push({
  cid: "j01", file: "j01_clean_en_table_image_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "clean_en_table_image",
  desc: "Clean English deck: readable sizes, native table, valid image with alt text, no overlap.",
  gt: [J("offslide_object", "negative", "all shapes inside the 16:9 canvas"),
       J("font_too_small", "negative", "explicit sizes 14-28pt"),
       J("text_overflow", "negative", "boxes tall enough for their text"),
       J("unfinished_placeholder", "negative", "real prose, no prompt"),
       J("media_broken", "negative", "valid embedded PNG"),
       J("broken_reference", "negative", "no internal/dangling relationship"),
       J("object_overlap", "negative", "table/image/title do not collide"),
       J("missing_alt_text", "negative", "picture has altText"),
       J("structure_anomaly", "negative", "valid pptx package with required parts")],
  build(p) {
    const s = p.addSlide();
    s.background = { color: "FFFFFF" };
    text(s, "Quarterly Review (PptxGenJS)", { fontSize: 28, bold: true, h: 0.8 });
    text(s, "Revenue rose through the year; the Q4 launch drove the strongest quarter.",
      { y: 1.45, w: 11.8, h: 0.9, fontSize: 18 });
    table(s, [
      [{ text: "Quarter", options: { bold: true } }, { text: "Revenue", options: { bold: true } }, { text: "Growth", options: { bold: true } }],
      [{ text: "Q1" }, { text: "$1.2M" }, { text: "+8%" }],
      [{ text: "Q4" }, { text: "$1.8M" }, { text: "+15%" }],
    ]);
    s.addImage({ data: pngUri([120, 160, 210]), x: 6.6, y: 2.3, w: 5.4, h: 3.2, altText: "Regional trend chart" });
  },
});

scenarios.push({
  cid: "j02", file: "j02_clean_zh_typeset_16x9.pptx", lang: "zh", aspect: "16:9",
  scenario: "clean_zh_typeset",
  desc: "Well-typeset Chinese: full-width punctuation, one normal CJK-Latin space.",
  gt: [J("cjk_typography", "negative", "full-width punctuation, single normal space, no forbidden start"),
       J("unfinished_placeholder", "negative", "real Chinese prose"),
       J("blank_slide", "negative", "content present")],
  build(p) {
    const s = p.addSlide();
    s.background = { color: "FFFFFF" };
    text(s, "中文排版规范示例", { fontSize: 28, bold: true, fontFace: "Microsoft YaHei" });
    text(s, "本页使用微软雅黑，中文与 English、数字 123 之间保留单个空格，标点为全角，例如：你好，世界。",
      { y: 1.55, w: 11.8, h: 1.6, fontSize: 20, fontFace: "Microsoft YaHei" });
  },
});

scenarios.push({
  cid: "j03", file: "j03_clean_mixed_4x3.pptx", lang: "mixed", aspect: "4:3",
  scenario: "clean_4_3",
  desc: "4:3 bilingual clean slide authored within the narrower canvas.",
  gt: [J("offslide_object", "negative", "all boxes inside 4:3 bounds"),
       J("text_overflow", "negative", "ample boxes"),
       J("blank_slide", "negative", "content present"),
       J("cjk_typography", "negative", "normal punctuation and spacing")],
  build(p) {
    const s = p.addSlide();
    text(s, "4:3 Bilingual Slide / 双语页面", { w: 8.8, fontSize: 26, bold: true });
    text(s, "Project 名称 Name 使用规范标点与间距，内容完整无占位。",
      { x: 0.45, y: 1.5, w: 8.9, h: 1.2, fontSize: 18, fontFace: "Microsoft YaHei" });
  },
});

scenarios.push({
  cid: "j04", file: "j04_offslide_shape_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "pos_offslide",
  desc: "Rectangle fully to the right of the 13.333in canvas.",
  gt: [J("offslide_object", "positive", "shape x=14in beyond canvas width", { count: 1 })],
  build(p) {
    const s = p.addSlide();
    text(s, "Off-slide card");
    rect(s, { x: 14, y: 3.0, w: 2.2, h: 1.4 }, "FFCCCC");
  },
});

scenarios.push({
  cid: "j05", file: "j05_overflow_nowrap_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "pos_overflow",
  desc: "24pt unwrapped text in a very short box; height clearly insufficient.",
  gt: [J("text_overflow", "positive", "wrap disabled; tiny height; explicit 24pt", { count: 1 })],
  build(p) {
    const s = p.addSlide();
    text(s, "Overflow sample", { y: 0.4 });
    s.addText("A long unwrapped sentence that cannot fit a tiny vertical box.",
      { x: 0.55, y: 1.8, w: 11.6, h: 0.18, fontSize: 24, wrap: false });
  },
});

scenarios.push({
  cid: "j06", file: "j06_font_small_10pt_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "pos_font_small",
  desc: "Explicit 10pt footnote below the 12pt minimum; box ample to isolate the defect.",
  gt: [J("font_too_small", "positive", "explicit 10pt < 12pt", { count: 1 }),
       J("text_overflow", "negative", "box height ample for the short line")],
  build(p) {
    const s = p.addSlide();
    text(s, "Small footnote", { fontSize: 24, bold: true });
    s.addText("Internal footnote: data shown for illustration only.",
      { x: 0.55, y: 3.1, w: 11.6, h: 0.5, fontSize: 10 });
  },
});

scenarios.push({
  cid: "j07", file: "j07_overlap_cards_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "pos_overlap",
  desc: "Two plain content rectangles overlap beyond 30% of the smaller shape.",
  gt: [J("object_overlap", "positive", "plain cards overlap >=30%", { count: 1 }, { profiles: "full" })],
  build(p) {
    const s = p.addSlide();
    text(s, "Colliding cards");
    rect(s, { x: 1.8, y: 1.9, w: 4.4, h: 2.3 }, "CCDDFF");
    rect(s, { x: 3.8, y: 2.7, w: 4.4, h: 2.3 }, "FFDDCC");
  },
});

scenarios.push({
  cid: "j08", file: "j08_blank_slide_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "pos_blank",
  desc: "Empty slide with no shapes.",
  gt: [J("blank_slide", "positive", "slide contains no content shape or media", { count: 1 }, { profiles: "full" })],
  build(p) { p.addSlide(); },
});

scenarios.push({
  cid: "j09", file: "j09_placeholder_text_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "pos_placeholder",
  desc: "English placeholder leftovers (click prompt, TODO, Lorem ipsum).",
  gt: [J("unfinished_placeholder", "positive", "three prompt texts", { count: 3 })],
  build(p) {
    const s = p.addSlide();
    text(s, "Click to add title", { y: 0.4, fontSize: 28 });
    text(s, "TODO: insert the Q3 figures before review", { y: 1.7, fontSize: 18 });
    text(s, "Lorem ipsum dolor sit amet.", { y: 2.7, fontSize: 18 });
  },
});

scenarios.push({
  cid: "j10", file: "j10_missing_alt_image_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "pos_missing_alt",
  desc: "Visible image without altText; valid bytes.",
  gt: [J("missing_alt_text", "positive", "image omits altText", { count: 1 }, { profiles: "full" }),
       J("media_broken", "negative", "PNG bytes decode successfully")],
  build(p) {
    const s = p.addSlide();
    text(s, "No-alt image");
    s.addImage({ data: pngUri([150, 150, 200]), x: 2.2, y: 1.8, w: 4.4, h: 2.8 });
  },
});

scenarios.push({
  cid: "j11", file: "j11_clean_images_table_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "clean_images_table",
  desc: "Healthy images with alt text and a table; no defects.",
  gt: [J("media_broken", "negative", "all embedded PNGs valid"),
       J("missing_alt_text", "negative", "all pictures carry altText"),
       J("structure_anomaly", "negative", "well-formed OOXML package"),
       J("blank_slide", "negative", "content present")],
  build(p) {
    const s = p.addSlide();
    text(s, "Asset Gallery");
    s.addImage({ data: pngUri([180, 100, 100]), x: 0.7, y: 1.8, w: 3.4, h: 2.4, altText: "Photo alpha" });
    s.addImage({ data: pngUri([100, 180, 120]), x: 4.4, y: 1.8, w: 3.4, h: 2.4, altText: "Photo beta" });
    s.addImage({ data: pngUri([120, 120, 200]), x: 8.1, y: 1.8, w: 3.4, h: 2.4, altText: "Photo gamma" });
  },
});

scenarios.push({
  cid: "j12", file: "j12_low_contrast_gray_16x9.pptx", lang: "zh", aspect: "16:9",
  scenario: "pos_contrast",
  desc: "12pt light-gray text on explicit white background, below 4.5:1.",
  gt: [J("low_contrast", "positive", "gray on white below normal contrast threshold", { count: 1 }, { profiles: "full" })],
  build(p) {
    const s = p.addSlide();
    s.background = { color: "FFFFFF" };
    text(s, "浅灰文字对比度不足", { y: 1.8, fontSize: 12, color: "CCCCCC", fontFace: "Microsoft YaHei" });
  },
});

scenarios.push({
  cid: "j13", file: "j13_cjk_issues_16x9.pptx", lang: "zh", aspect: "16:9",
  scenario: "pos_cjk",
  desc: "Kinsoku line-start comma plus half-width comma after CJK.",
  gt: [J("cjk_typography", "positive", "kinsoku_line_start + halfwidth_punct", { count: 1 }, { profiles: "full" })],
  build(p) {
    const s = p.addSlide();
    text(s, "中文排版问题", { fontSize: 26, bold: true, fontFace: "Microsoft YaHei" });
    s.addText("，逗号不应出现在行首。", { x: 0.55, y: 1.7, w: 11.6, h: 0.6, fontSize: 22, fontFace: "Microsoft YaHei" });
    s.addText("你好,世界使用了半角逗号。", { x: 0.55, y: 2.7, w: 11.6, h: 0.6, fontSize: 22, fontFace: "Microsoft YaHei" });
  },
});

scenarios.push({
  cid: "j14", file: "j14_clean_shape_grid_16x9.pptx", lang: "en", aspect: "16:9",
  scenario: "clean_grid",
  desc: "A separated grid of small accent squares; no overlap, all inside canvas.",
  gt: [J("object_overlap", "negative", "grid squares are separated with gaps"),
       J("offslide_object", "negative", "grid remains inside canvas"),
       J("blank_slide", "negative", "shapes present")],
  build(p) {
    const s = p.addSlide();
    text(s, "Separated grid");
    for (let r = 0; r < 3; r++) for (let c = 0; c < 6; c++) {
      rect(s, { x: 0.7 + c * 1.05, y: 1.9 + r * 1.1, w: 0.85, h: 0.85 },
        `88${(r * 6 + c) % 2 ? "AA" : "CC"}EE`.toUpperCase());
    }
  },
});

async function main() {
  const records = [];
  for (const sc of scenarios) {
    const p = deck(sc.aspect);
    sc.build(p);
    await save(p, sc.file);
    records.push(rec(sc.cid, `pptxgenjs/${sc.file}`, sc.lang, sc.aspect,
      sc.scenario, sc.desc, sc.gt));
  }
  const partPath = path.join(OUT_DIR, "manifest_part.json");
  fs.writeFileSync(partPath, JSON.stringify(records, null, 2), "utf-8");
  console.log(`pptxgenjs records: ${records.length}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
