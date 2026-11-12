// 示範版用的模擬排行榜：成績只存在這台瀏覽器，不會送到正式網站。
(function () {
  "use strict";
  var KEY = "nekoSudokuDemoScores.v1";
  function load() {
    try { var d = JSON.parse(localStorage.getItem(KEY)); if (Array.isArray(d)) return d; } catch (e) {}
    return [];
  }
  function save(list) { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {} }
  function today() {
    var d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function sorted(list) {
    return list.slice().sort(function (a, b) { return a.time - b.time || a.mistakes - b.mistakes || a.at - b.at; });
  }
  function pub(s) { return { id: s.id, name: s.name, time: s.time, attempt: s.attempt, mistakes: s.mistakes, at: s.at }; }
  function json(status, body) {
    return new Response(JSON.stringify(body), { status: status, headers: { "Content-Type": "application/json" } });
  }
  function handle(method, url, body) {
    var all = load();
    var p = url.pathname.replace(/^.*\/api\//, "/api/");
    if (p === "/api/scores/today") {
      var day = today();
      var groups = {};
      all.filter(function (s) { return s.day === day; }).forEach(function (s) {
        (groups[s.key] = groups[s.key] || []).push(s);
      });
      var out = Object.keys(groups).sort().map(function (k) {
        var list = sorted(groups[k]);
        var parts = k.split("-");
        return { size: Number(parts[0]), variant: Number(parts[1]), count: list.length, best: list[0].time, scores: list.map(pub) };
      });
      return json(200, { date: day, groups: out });
    }
    if (p === "/api/scores" && method === "GET") {
      var key = url.searchParams.get("key") || "";
      var limit = Number(url.searchParams.get("limit")) || 10;
      var list = sorted(all.filter(function (s) { return s.key === key; }));
      return json(200, { key: key, best: list.length ? list[0].time : null, scores: list.slice(0, limit).map(pub), total: list.length });
    }
    if (p === "/api/scores" && method === "POST") {
      if (!body || !body.key || !(body.time > 0)) return json(400, { error: "成績格式不正確" });
      var entry = {
        id: "demo-" + Date.now().toString(36), key: String(body.key),
        name: String(body.name || "未命名").slice(0, 20), time: Math.round(body.time),
        attempt: Number(body.attempt) || 1, mistakes: Number(body.mistakes) || 0,
        at: Date.now(), day: today()
      };
      all.push(entry);
      save(all);
      var same = sorted(all.filter(function (s) { return s.key === entry.key; }));
      var rank = same.findIndex(function (s) { return s.id === entry.id; }) + 1;
      return json(200, { rank: rank, total: same.length, scores: same.slice(0, 10).map(pub), entry: { id: entry.id } });
    }
    return json(404, { error: "示範版沒有這個功能" });
  }
  var realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init || {};
    var url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.pathname.indexOf("/api/") === -1) return realFetch(input, init);
    var body = null;
    try { body = init.body ? JSON.parse(init.body) : null; } catch (e) {}
    var method = (init.method || "GET").toUpperCase();
    return new Promise(function (resolve) { setTimeout(function () { resolve(handle(method, url, body)); }, 120); });
  };
  window.__nekoDemoReset = function () { localStorage.removeItem(KEY); location.reload(); };
})();
