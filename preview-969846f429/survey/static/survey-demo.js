// 示範版用的模擬後端：所有資料只存在這台瀏覽器，不會送到正式網站。
(function () {
  "use strict";

  const KEY = "mathLogicSurveyDemo.v1";
  const CATEGORIES = [
    "1. 我覺得這個習慣/做法很具有數學邏輯",
    "2. 我受不了這些沒有數學/邏輯的行為",
    "3. 我會運用數學邏輯的思維進行什麼事?",
    "4. 如果我的數學邏輯更強一點，在【什麼事上】應該可以更如魚得水?",
    "5. 其他【我就是有話要說】",
  ];
  // 範例回答（虛構）
  const SEED = [
    ["小明", 1, "去超市前先把清單照走道順序排好，繞一圈就買完，不會來回跑。"],
    ["阿芳", 2, "排隊結帳明明有空的櫃檯，大家還是擠在同一排。"],
    ["數學教室 A 組", 3, "比價的時候會換算成每 100 公克多少錢，不只看總價。"],
    ["Kevin", 4, "安排出遊行程，可以更快算出怎麼走最省時間。"],
    ["小花", 5, "原來我每天都在用邏輯，只是以前沒發現。"],
  ];
  const INCOMING = [
    ["阿哲", 2, "電梯明明快到了還一直按關門鍵。"],
    ["Mia", 3, "用平均每天花多少錢來決定要不要買年票。"],
    ["王老師", 1, "收納抽屜按使用頻率分區，常用的放最前面。"],
    ["小宇", 4, "看懂手機方案的計費方式，不會被綁約。"],
    ["Jenny", 5, "希望下次活動可以有更多小組討論時間！"],
    ["阿德", 3, "煮飯時同時開兩個爐子，用時間差把菜一起做好。"],
  ];

  const nowIso = (offsetSec = 0) => new Date(Date.now() - offsetSec * 1000).toISOString();

  function fresh() {
    const db = { seq: 0, participants: {}, responses: [], sim: 0, lastSim: Date.now() };
    SEED.forEach(([nickname, category, text], i) => {
      const pid = "demo-p" + i;
      db.participants[pid] = { id: pid, nickname, finished: i % 2 === 0 };
      db.seq += 1;
      db.responses.push({
        id: "demo-r" + db.seq, seq: db.seq, participantId: pid, nickname, category, text,
        createdAt: nowIso((SEED.length - i) * 240), highlight: i === 2, adminNote: "",
      });
    });
    return db;
  }

  function load() {
    try {
      const db = JSON.parse(localStorage.getItem(KEY));
      if (db && Array.isArray(db.responses)) return db;
    } catch (e) { /* ignore */ }
    return fresh();
  }
  function save(db) {
    try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) { /* ignore */ }
  }

  // 每 8 秒模擬一位新的參加者送出回答（最多 6 則），方便看即時觀看的效果
  function simulate(db) {
    if (db.sim >= INCOMING.length) return;
    if (Date.now() - db.lastSim < 8000) return;
    const [nickname, category, text] = INCOMING[db.sim];
    const pid = "demo-sim" + db.sim;
    db.participants[pid] = { id: pid, nickname, finished: false };
    db.seq += 1;
    db.responses.push({
      id: "demo-r" + db.seq, seq: db.seq, participantId: pid, nickname, category, text,
      createdAt: nowIso(), highlight: false, adminNote: "",
    });
    db.sim += 1;
    db.lastSim = Date.now();
  }

  const pub = (r) => ({ id: r.id, seq: r.seq, nickname: r.nickname, category: r.category, text: r.text, createdAt: r.createdAt });

  function summary(db) {
    const categoryCounts = {};
    const latestByCategory = {};
    CATEGORIES.forEach((_, i) => { categoryCounts[String(i + 1)] = 0; });
    db.responses.forEach((r) => {
      categoryCounts[String(r.category)] += 1;
      latestByCategory[String(r.category)] = r.createdAt;
    });
    const parts = Object.values(db.participants);
    return {
      totalResponses: db.responses.length,
      participants: parts.length,
      finishedParticipants: parts.filter((p) => p.finished).length,
      highlighted: db.responses.filter((r) => r.highlight).length,
      categoryCounts,
      latestByCategory,
      latestSeq: db.seq,
    };
  }

  // 匯出時在 = + - @ 開頭的內容前加 '，避免 Excel 當成公式
  function csvCell(value) {
    let text = String(value == null ? "" : value);
    if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }

  const json = (status, body) => new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json" },
  });
  const isAdmin = () => sessionStorage.getItem(KEY + ".admin") === "1";

  function handle(method, url, body) {
    const db = load();
    const p = url.pathname.replace(/^.*\/api\//, "/api/");
    const q = url.searchParams;

    if (p === "/api/config") {
      const base = location.href.split("#")[0];
      return json(200, {
        title: "【八大智能數學邏輯組】你的生活想法被數學邏輯影響嗎？（示範版）",
        categories: CATEGORIES, baseUrl: base, joinUrl: base + "#/join",
      });
    }
    if (p === "/api/summary") { simulate(db); save(db); return json(200, summary(db)); }
    if (p === "/api/join" && method === "POST") {
      const nickname = String((body && body.nickname) || "").trim();
      if (!nickname) return json(400, { error: "請輸入參加者暱稱。" });
      const id = "demo-u" + Date.now().toString(36);
      db.participants[id] = { id, nickname, finished: false };
      save(db);
      return json(200, { participant: { id, nickname } });
    }
    if (p === "/api/finish" && method === "POST") {
      const part = db.participants[body && body.participantId];
      if (part) part.finished = true;
      save(db);
      return json(200, { ok: true });
    }
    if (p === "/api/responses" && method === "GET") {
      simulate(db); save(db);
      const after = Number(q.get("after")) || 0;
      const cat = Number(q.get("category")) || 0;
      const list = db.responses.filter((r) => r.seq > after && (!cat || r.category === cat)).map(pub);
      return json(200, { categories: CATEGORIES, latestSeq: db.seq, responses: list });
    }
    if (p === "/api/responses" && method === "POST") {
      const part = db.participants[body && body.participantId];
      const category = Number(body && body.category);
      const text = String((body && body.text) || "").trim();
      if (!part) return json(400, { error: "找不到參加者資料，請重新輸入暱稱。" });
      if (!(category >= 1 && category <= CATEGORIES.length)) return json(400, { error: "回答類別不正確。" });
      if (!text) return json(400, { error: "請填寫你的回答。" });
      db.seq += 1;
      const r = { id: "demo-r" + db.seq, seq: db.seq, participantId: part.id, nickname: part.nickname, category, text: text.slice(0, 2000), createdAt: nowIso(), highlight: false, adminNote: "" };
      db.responses.push(r);
      save(db);
      return json(200, { response: pub(r) });
    }

    // ---- 後台（示範版密碼：demo）----
    if (p === "/api/admin/session") return json(200, { authenticated: isAdmin() });
    if (p === "/api/admin/login" && method === "POST") {
      if ((body && body.password) !== "demo") return json(401, { error: "密碼不正確（示範版密碼是 demo）。" });
      sessionStorage.setItem(KEY + ".admin", "1");
      return json(200, { ok: true });
    }
    if (p === "/api/admin/logout") { sessionStorage.removeItem(KEY + ".admin"); return json(200, { ok: true }); }
    if (p.startsWith("/api/admin/") && !isAdmin()) return json(401, { error: "請先登入後台。" });
    if (p === "/api/admin/summary") return json(200, summary(db));
    if (p === "/api/admin/responses" && method === "GET") return json(200, { responses: db.responses });
    const m = p.match(/^\/api\/admin\/responses\/([^/]+)$/);
    if (m) {
      const i = db.responses.findIndex((r) => r.id === decodeURIComponent(m[1]));
      if (i < 0) return json(404, { error: "找不到這則回答。" });
      if (method === "DELETE") { db.responses.splice(i, 1); save(db); return json(200, { ok: true }); }
      if (method === "PATCH") {
        if (body && "highlight" in body) db.responses[i].highlight = Boolean(body.highlight);
        if (body && "adminNote" in body) db.responses[i].adminNote = String(body.adminNote || "").slice(0, 2000);
        save(db);
        return json(200, { response: db.responses[i] });
      }
    }
    if (p === "/api/admin/export.csv") {
      const cat = Number(q.get("category")) || 0;
      const onlyHi = q.get("highlight") === "1";
      const rows = db.responses.filter((r) => (!cat || r.category === cat) && (!onlyHi || r.highlight));
      const lines = [["編號", "暱稱", "類別", "回答", "時間", "精選", "備註"].map(csvCell).join(",")];
      rows.forEach((r) => lines.push([r.seq, r.nickname, CATEGORIES[r.category - 1], r.text, r.createdAt, r.highlight ? "是" : "", r.adminNote].map(csvCell).join(",")));
      return new Response("﻿" + lines.join("\r\n"), { status: 200, headers: { "Content-Type": "text/csv; charset=utf-8" } });
    }
    return json(404, { error: "示範版沒有這個功能。" });
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = function (input, init = {}) {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.includes("/api/")) return realFetch(input, init);
    let body = null;
    try { body = init.body ? JSON.parse(init.body) : null; } catch (e) { body = null; }
    const method = (init.method || "GET").toUpperCase();
    return new Promise((resolve) => setTimeout(() => resolve(handle(method, url, body)), 120));
  };

  window.__surveyDemoReset = function () {
    localStorage.removeItem(KEY);
    sessionStorage.removeItem(KEY + ".admin");
    localStorage.removeItem("mathLogicSurveyParticipant");
    location.reload();
  };
})();
