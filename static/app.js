"use strict";

/* ================= 全局状态 ================= */
const state = {
  lesson: null,    // 服务端文章数据
  units: [],       // 带段落分隔的展示单元 {ch,s,f,l,br}
  targets: [],     // 只含“要打的字符”，用于比对
  prevText: "",    // 打字框上一次内容，用来数新错的字
  match: 0,        // 从开头起连续正确的字数
  errors: 0,
  startAt: null,
  finished: false,
  composing: false,
  refData: null,
};

const $ = (id) => document.getElementById(id);
const CJK = /^[\u4e00-\u9fff]$/;
const pad4 = (code) => (code || "").toUpperCase().padEnd(4, "_");
const esc = (s) => s.replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

/* ================= 小工具 ================= */
function setStatus(msg, cls) {
  const el = $("status");
  el.className = "status" + (cls ? " " + cls : "");
  el.textContent = msg;
}

function fmtTime(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return String(m).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}

function commonPrefix(a, b) {
  const n = Math.min(a.length, b.length);
  let i = 0;
  while (i < n && a[i] === b[i]) i++;
  return i;
}

/* ================= 86 字根键盘 ================= */
const KB_ROWS = [
  ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
  ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
  ["Z", "X", "C", "V", "B", "N", "M"],
];
const KB_ROOTS = {
  G: "王 一 五 戋",
  F: "土 士 二 干 十 寸 雨",
  D: "大 犬 三 古 石 厂",
  S: "木 丁 西",
  A: "工 戈 艹 匚 七",
  H: "目 上 止 卜 丨 虍",
  J: "日 早 刂 虫",
  K: "口 川",
  L: "田 甲 囗 四 车 力",
  M: "山 由 贝 冂 几",
  T: "禾 竹 丿 彳 攵 夂",
  R: "白 手 扌 斤",
  E: "月 彡 乃 用 豕 衣",
  W: "人 亻 八",
  Q: "金 钅 勹 儿 夕 犭",
  Y: "言 讠 文 方 广 丶 亠",
  U: "立 辛 丬 六 门 疒",
  I: "水 氵 小",
  O: "火 业 灬 米",
  P: "之 辶 宀 冖 礻 衤",
  N: "己 巳 已 乙 尸 心 忄 羽",
  B: "子 孑 耳 了 也 凵",
  V: "女 刀 九 臼 彐",
  C: "又 巴 马 厶",
  X: "纟 幺 弓 匕",
  Z: "万能键",
};
const KB_KEYS = {};

function zoneOf(ch) {
  if ("GFDSA".includes(ch)) return "zone1";
  if ("HJKLM".includes(ch)) return "zone2";
  if ("TREWQ".includes(ch)) return "zone3";
  if ("YUIOP".includes(ch)) return "zone4";
  if ("NBVCX".includes(ch)) return "zone5";
  return "zoneZ";
}

function buildKeyboard() {
  const kb = $("kb");
  if (!kb) return;
  const frag = document.createDocumentFragment();
  KB_ROWS.forEach((row, ri) => {
    const rowEl = document.createElement("div");
    rowEl.className = "kb-row" + (ri === 1 ? " off1" : ri === 2 ? " off2" : "");
    for (const ch of row) {
      const el = document.createElement("div");
      el.className = "key " + zoneOf(ch);
      el.id = "kb-" + ch;
      el.title = ch + " 键：字根 " + (KB_ROOTS[ch] || "");
      const kl = document.createElement("span");
      kl.className = "kl";
      kl.textContent = ch;
      const kr = document.createElement("span");
      kr.className = "kr";
      kr.textContent = KB_ROOTS[ch] || "";
      el.append(kl, kr);
      KB_KEYS[ch] = el;
      rowEl.appendChild(el);
    }
    frag.appendChild(rowEl);
  });
  kb.replaceChildren(frag);
}

function lightKey(letter, ms = 170) {
  const el = KB_KEYS[(letter || "").toUpperCase()];
  if (!el) return;
  el.classList.add("down");
  clearTimeout(el._kbT);
  el._kbT = setTimeout(() => el.classList.remove("down"), ms);
}

function targetUnitAt(match) {
  let seen = 0;
  for (const u of state.units) {
    if (u.br) continue;
    if (seen === match) return u;
    seen++;
  }
  return null;
}

function updateKeyHints() {
  document.querySelectorAll(".key.next").forEach((el) => el.classList.remove("next"));
  if (!$("chk-hint").checked) return;
  const u = targetUnitAt(state.match);
  if (!u || !u.s) return;
  const code = ($("chk-jian").checked ? u.s : u.f) || "";
  for (const ch of code.toUpperCase()) {
    const el = KB_KEYS[ch];
    if (el) el.classList.add("next");
  }
}

/* ================= 练习准备 ================= */
function prepareUnits(limitChars) {
  const items = [];
  const paras = state.lesson.paragraphs || [];
  for (let p = 0; p < paras.length; p++) {
    if (p > 0 && items.length) items.push({ br: true });
    for (const u of paras[p].units || []) {
      items.push({ ch: u.ch, s: u.s, f: u.f, l: u.l, br: false });
    }
  }
  if (limitChars > 0) {
    let n = 0, cut = items.length;
    for (let i = 0; i < items.length; i++) {
      if (items[i].br) continue;
      n++;
      if (n >= limitChars) { cut = i + 1; break; }
    }
    items.length = cut;
  }
  while (items.length && items[items.length - 1].br) items.pop();

  state.units = items;
  state.targets = items.filter((u) => !u.br).map((u) => u.ch);
  state.prevText = "";
  state.match = 0;
  state.errors = 0;
  state.startAt = null;
  state.finished = false;

  const ta = $("type-input");
  ta.value = "";
  ta.maxLength = state.targets.length;
  ta.readOnly = false;
}

/* ================= 渲染 ================= */
function renderText() {
  // 上方原文 + 码标注；当前要打的字用红框标出
  const view = $("text-view");
  const showCode = $("chk-code").checked;
  const jian = $("chk-jian").checked;
  const N = state.targets.length;
  const from = Math.max(0, state.match - 10);
  const to = Math.min(N - 1, state.match + 55);
  const frag = document.createDocumentFragment();
  let seen = 0;
  let started = false;

  if (state.match > 10) {
    const el = document.createElement("span");
    el.className = "ellipsis";
    el.textContent = "… ";
    frag.appendChild(el);
  }

  for (const u of state.units) {
    if (u.br) {
      if (started) {
        const gap = document.createElement("span");
        gap.className = "gap";
        frag.appendChild(gap);
      }
      continue;
    }
    const j = seen++;
    if (j < from) continue;
    if (j > to) break;
    started = true;

    const span = document.createElement("span");
    const cls = ["unit"];
    if (j < state.match) cls.push("done");
    if (j === state.match) cls.push("current");
    if (CJK.test(u.ch)) {
      cls.push(u.l === 1 ? "lvl1" : u.l === 2 ? "lvl2" : u.l === 3 ? "lvl3" : "");
    } else if (u.s) {
      cls.push("plain");
    } else {
      cls.push("punct");
    }
    span.className = cls.join(" ").trim();

    const han = document.createElement("span");
    han.className = "han";
    han.textContent = u.ch;
    span.appendChild(han);

    const sub = document.createElement("span");
    sub.className = "subc";
    if (showCode && u.s) {
      const code = jian ? u.s : u.f;
      sub.textContent = pad4(code);
      const level = u.l === 1 ? "一级简码"
        : u.l === 2 ? "二级简码"
        : u.l === 3 ? "三级简码" : "全码";
      span.title = u.ch + "：应打 " + pad4(code) + "（" + level + "；全码 " +
        (u.f || "无") + "）";
    } else if (showCode) {
      sub.textContent = "　";
      sub.classList.add("no-code");
    }
    span.appendChild(sub);
    frag.appendChild(span);
  }

  if (state.match + 55 < N) {
    const el = document.createElement("span");
    el.className = "ellipsis";
    el.textContent = "…";
    frag.appendChild(el);
  }
  view.replaceChildren(frag);
  // 单行横向滚动：让当前字始终停在可视区域中间
  const cur = view.querySelector(".unit.current");
  if (cur) {
    view.scrollLeft = Math.max(0,
      cur.offsetLeft + cur.offsetWidth / 2 - view.clientWidth / 2);
  }
}

function renderMirror() {
  // 下方打字框：把用户输入逐字画成 绿=正确 / 红=错
  const mirror = $("mirror");
  const text = $("type-input").value;
  const targets = state.targets;
  const frag = document.createDocumentFragment();
  for (let i = 0; i < text.length; i++) {
    const span = document.createElement("span");
    if (i < targets.length) {
      span.className = text[i] === targets[i] ? "ok" : "err";
    } else {
      span.className = "extra";
    }
    span.textContent = text[i];
    frag.appendChild(span);
  }
  mirror.replaceChildren(frag);
  syncMirrorScroll();
}

function renderStats() {
  const N = state.targets.length;
  const done = state.match;
  $("st-progress").textContent = done + " / " + N;
  $("st-err").textContent = state.errors;
  let speed = 0;
  if (state.startAt && done > 0) {
    const ms = Date.now() - state.startAt;
    speed = ms > 0 ? (done / ms) * 60000 : 0;
  }
  $("st-speed").textContent = speed.toFixed(1);
  const acc = done + state.errors > 0
    ? (done / (done + state.errors)) * 100 : 100;
  $("st-acc").textContent = acc.toFixed(1) + "%";
  $("st-time").textContent = fmtTime(state.startAt ? Date.now() - state.startAt : 0);
  $("done-banner").hidden = !state.finished;
}

function renderMeta() {
  const m = state.lesson.meta || {};
  const st = state.lesson.stats || {};
  $("meta").innerHTML =
    "<h2>" + esc(m.title || "") + "</h2>" +
    (m.subtitle ? "<div>" + esc(m.subtitle) + "</div>" : "") +
    '<div class="src">' +
      "人民日报 " + esc(m.date || "") +
      (m.author ? "　作者：" + esc(m.author) : "") +
      "　全文 " + (st.chars || 0) + " 字" +
      (st.missing && st.missing.length
        ? "　（缺码 " + esc(st.missing.join("")) + "）" : "") +
    "</div>";
}

function renderAll() {
  renderMeta();
  renderText();
  renderMirror();
  renderStats();
  updateKeyHints();
}

function syncMirrorScroll() {
  const ta = $("type-input");
  const mirror = $("mirror");
  if (ta.selectionStart === ta.value.length && ta.value.length) {
    ta.scrollTop = ta.scrollHeight;
  }
  mirror.scrollTop = ta.scrollTop;
  mirror.scrollLeft = ta.scrollLeft;
}

/* ================= 打字判定 ================= */
function onChange() {
  const ta = $("type-input");
  if (state.finished) return; // 已完成，只读
  const cur = ta.value;
  const prev = state.prevText;

  if (!state.startAt && cur.length) state.startAt = Date.now();

  // 只有“新增了字符”才可能产生新错字；删除/退格不计错
  if (cur.length > prev.length) {
    const p = commonPrefix(prev, cur);
    const added = cur.length - prev.length;
    for (let k = 0; k < added; k++) {
      const idx = p + k; // 插入字符在文本框中的绝对位置
      if (idx < state.targets.length && cur[idx] !== state.targets[idx]) {
        state.errors++;
      }
    }
  }

  state.prevText = cur;
  state.match = 0;
  const n = Math.min(cur.length, state.targets.length);
  while (state.match < n &&
         cur[state.match] === state.targets[state.match]) {
    state.match++;
  }

  if (state.targets.length > 0 && state.match >= state.targets.length) {
    state.finished = true;
    ta.readOnly = true;
  }
  renderAll();
}

function bindInput() {
  const ta = $("type-input");
  $("typebox").addEventListener("click", () => ta.focus());

  let compPrev = "";
  ta.addEventListener("compositionstart", () => {
    state.composing = true;
    compPrev = "";
  });
  ta.addEventListener("compositionupdate", (e) => {
    const letters = String(e.data || "").replace(/[^A-Za-z]/g, "");
    if (letters.length > compPrev.length) {
      lightKey(letters[letters.length - 1], 320);
    }
    compPrev = letters;
  });
  ta.addEventListener("compositionend", () => {
    state.composing = false;
    compPrev = "";
    onChange();
  });
  ta.addEventListener("input", () => {
    if (!state.composing) onChange();
  });
  ta.addEventListener("scroll", syncMirrorScroll);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v") {
      e.preventDefault();
      return;
    }
  });
  ta.addEventListener("paste", (e) => e.preventDefault());
  ta.addEventListener("drop", (e) => e.preventDefault());

  window.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (k && /^[a-z]$/i.test(k)) lightKey(k, 170);
  });
}

function restart() {
  const limit = parseInt($("len-sel").value, 10) || 0;
  prepareUnits(limit);
  $("lesson-card").hidden = false;
  renderAll();
  $("type-input").focus();
}

/* ================= 抓取与文章切换 ================= */
function todayStr() {
  const t = new Date();
  return t.getFullYear() + "-" +
    String(t.getMonth() + 1).padStart(2, "0") + "-" +
    String(t.getDate()).padStart(2, "0");
}

function preferedItem(items) {
  const re = /(社论|评论员|人民时评|时评|钟声|来论|思想纵横|评论观察)/;
  const hit = items.find((it) => re.test(it.title));
  if (hit) return hit;
  const news = items.find((it) => /评论/.test(it.section));
  if (news) return news;
  const firstPage = items.filter((it) => it.page === 1);
  const pool = firstPage.length ? firstPage : items;
  return pool.reduce((a, b) => (a.title.length >= b.title.length ? a : b));
}

async function loadEditions(dateStr) {
  setStatus("正在抓取人民日报版面…");
  $("article-sel").disabled = true;
  let data;
  try {
    const resp = await fetch("/api/editions?date=" + encodeURIComponent(dateStr));
    data = await resp.json();
    if (!data.ok) throw new Error(data.error || "抓取失败");
  } catch (err) {
    setStatus("在线抓取失败：" + err.message, "err");
    await tryLatestCache();
    return;
  }
  const ed = data.edition;
  const items = ed.items || [];
  if (!items.length) {
    setStatus(ed.date + " 没有可用文章。", "err");
    $("article-sel").disabled = false;
    return;
  }
  const sel = $("article-sel");
  sel.innerHTML = "";
  const note = ed.back > 0 ? "（最近一期为 " + ed.date + "，当天无报）" : "";
  setStatus("已获取人民日报 " + ed.date + " " + ed.weekday + note +
    "，共 " + items.length + " 篇，正在加载推荐文章…", "ok");
  items.forEach((it) => {
    const opt = document.createElement("option");
    opt.value = JSON.stringify({ id: it.id, date: ed.date });
    opt.textContent = "[" + (it.section || "?") + "] " + it.title;
    sel.appendChild(opt);
  });
  const pick = preferedItem(items);
  sel.value = JSON.stringify({ id: pick.id, date: ed.date });
  sel.disabled = false;
  await loadArticle(pick.id, ed.date);
}

async function loadArticle(id, dateStr) {
  $("article-sel").disabled = true;
  setStatus("正在抓取文章正文…");
  try {
    const resp = await fetch("/api/article?date=" + encodeURIComponent(dateStr) +
      "&id=" + encodeURIComponent(id));
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || "抓取失败");
    state.lesson = data.article;
    if (data.cached) {
      setStatus("文章已就绪（本地缓存，秒开）。", "ok");
    } else {
      setStatus("文章已就绪，点下方输入框开始跟打。", "ok");
    }
    restart();
    $("article-sel").disabled = false;
  } catch (err) {
    setStatus("文章抓取失败：" + err.message, "err");
    $("article-sel").disabled = false;
    await tryLatestCache();
  }
}

async function tryLatestCache() {
  try {
    const resp = await fetch("/api/latest");
    const data = await resp.json();
    if (data.ok && data.article) {
      state.lesson = data.article;
      setStatus("在线抓取失败，已加载最近一次练习文章。", "err");
      restart();
      return true;
    }
  } catch (e) { /* ignore */ }
  return false;
}

/* ================= 一/二级简码表 ================= */
async function openRef() {
  $("ref-mask").hidden = false;
  if (!state.refData) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    try {
      const resp = await fetch("/data/jianma.json", { signal: ctl.signal });
      state.refData = await resp.json();
    } catch (err) {
      $("ref-body").innerHTML =
        '<p class="loading">码表加载失败：' + esc(err.message) +
        "。请刷新页面后重试。</p>";
      return;
    } finally {
      clearTimeout(timer);
    }
  }
  renderRef();
  $("ref-search").focus();
}

function renderRef() {
  const d = state.refData;
  const q = $("ref-search").value.trim().toLowerCase();
  const keys = d.keys || [];
  let l1html = '<h3>一级简码（25 键，一键一字）</h3><div class="l1-grid">';
  for (const key of keys) {
    const ch = d.level1[key] || "";
    const hot = ch && q && (ch === q || key.toLowerCase() === q);
    l1html += '<div class="l1-item' + (hot ? " hl" : "") + '">' +
      "<b>" + esc(ch) + "</b><span class='k'>" + key + "___</span></div>";
  }
  l1html += "</div>";

  const lvl2 = d.level2 || {};
  let rows = "", matched = 0;
  for (const k1 of keys) {
    let cells = "";
    for (const k2 of keys) {
      const ch = lvl2[k1 + k2] || "";
      if (!ch) { cells += "<td class='empty'>·</td>"; continue; }
      const hot = q && (ch === q || (k1 + k2).toLowerCase() === q);
      if (hot) matched++;
      cells += "<td" + (hot ? " class='hl'" : "") + " title='" +
        esc(k1 + k2 + " " + ch) + "'>" + esc(ch) + "</td>";
    }
    rows += "<tr><td class='fkey'>" + k1 + "</td>" + cells + "</tr>";
  }
  const head = "<tr><th></th>" + keys.map((k) => "<th>" + k + "</th>").join("") + "</tr>";
  const hide = q && !matched;
  $("ref-body").innerHTML =
    l1html +
    '<h3>二级简码（2 键一字，共 ' + Object.keys(lvl2).length + " 个）</h3>" +
    '<div class="l2-wrap">' +
    (hide ? '<p class="loading">没有匹配的二级简码</p>'
          : "<table class='l2'>" + head + rows + "</table>") +
    "</div>";
}

/* ================= 事件绑定 ================= */
function bindUI() {
  $("date-input").value = todayStr();
  $("date-input").addEventListener("change", () => {
    loadEditions($("date-input").value);
  });
  $("btn-fetch").addEventListener("click", () => {
    loadEditions($("date-input").value);
  });
  $("article-sel").addEventListener("change", (e) => {
    const v = e.target.value;
    if (!v) return;
    const { id, date } = JSON.parse(v);
    loadArticle(id, date);
  });
  $("btn-restart").addEventListener("click", restart);
  $("len-sel").addEventListener("change", restart);
  $("chk-code").addEventListener("change", renderText);
  $("chk-jian").addEventListener("change", () => {
    renderText();
    updateKeyHints();
  });
  $("chk-kb").addEventListener("change", () => {
    $("kb-body").hidden = !$("chk-kb").checked;
  });
  $("chk-hint").addEventListener("change", updateKeyHints);
  $("btn-ref").addEventListener("click", openRef);
  $("btn-close-ref").addEventListener("click", () => { $("ref-mask").hidden = true; });
  $("ref-mask").addEventListener("click", (e) => {
    if (e.target === $("ref-mask")) $("ref-mask").hidden = true;
  });
  $("ref-search").addEventListener("input", renderRef);
}

/* ================= 启动 ================= */
window.addEventListener("DOMContentLoaded", () => {
  buildKeyboard();
  bindInput();
  bindUI();
  setInterval(() => { if (state.startAt && !state.finished) renderStats(); }, 1000);
  loadEditions(todayStr());
});
