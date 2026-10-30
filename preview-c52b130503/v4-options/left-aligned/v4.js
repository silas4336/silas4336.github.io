/* v4 互動：漸進增強，沒有 JS 時內容完整顯示 */
(function () {
  window.__v4 = 1;
  var root = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var each = function (sel, fn) { Array.prototype.forEach.call(document.querySelectorAll(sel), fn); };

  /* 主題：沒有存過就跟系統走 */
  var tBtn = document.querySelector(".theme");
  var isDark = function () {
    var t = root.dataset.theme;
    return t ? t === "dark" : !window.matchMedia("(prefers-color-scheme: light)").matches;
  };
  var paint = function () {
    if (!tBtn) return;
    tBtn.innerHTML = isDark()
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.2 14.6A8.5 8.5 0 0 1 9.4 3.8a8.5 8.5 0 1 0 10.8 10.8Z"/></svg>';
    tBtn.setAttribute("aria-label", isDark() ? (root.lang === "en" ? "Switch to light" : "切換為淺色") : (root.lang === "en" ? "Switch to dark" : "切換為深色"));
    each('meta[name="theme-color"]', function (m) { m.setAttribute("content", isDark() ? "#131314" : "#ffffff"); });
  };
  paint();
  if (tBtn) tBtn.addEventListener("click", function () {
    var next = isDark() ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (e) {}
    paint();
  });

  /* 進場 */
  var items = document.querySelectorAll(".rv");
  if ("IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.01 });
    Array.prototype.forEach.call(items, function (el) { io.observe(el); });
  } else {
    Array.prototype.forEach.call(items, function (el) { el.classList.add("in"); });
  }

  /* 主視覺：捲動時由縮小傾斜展開到正面 */
  var dev = document.querySelector(".device");
  if (dev && !reduce) {
    var queued = false;
    var tick = function () {
      queued = false;
      var r = dev.parentElement.getBoundingClientRect(), vh = window.innerHeight;
      var p = Math.min(1, Math.max(0, (vh - r.top) / (vh * 0.9)));
      var e = 1 - Math.pow(1 - p, 3);
      dev.style.transform = "rotateX(" + (18 * (1 - e)).toFixed(2) + "deg) scale(" + (0.86 + 0.14 * e).toFixed(4) + ")";
    };
    var schedule = function () { if (!queued) { queued = true; requestAnimationFrame(tick); } };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    schedule();
  }

  /* 幾何形狀跟著滑鼠輕微位移，深度不同位移量不同 */
  var shapes = document.querySelectorAll(".shapes .s[data-depth]");
  if (shapes.length && !reduce && window.matchMedia("(hover: hover)").matches) {
    var tx = 0, ty = 0, cx = 0, cy = 0, running = false;
    var drift = function () {
      cx += (tx - cx) * 0.06; cy += (ty - cy) * 0.06;
      Array.prototype.forEach.call(shapes, function (s) {
        var d = parseFloat(s.dataset.depth);
        s.style.transform = "translate3d(" + (cx * d).toFixed(1) + "px," + (cy * d).toFixed(1) + "px,0)";
      });
      if (Math.abs(tx - cx) + Math.abs(ty - cy) > 0.001) requestAnimationFrame(drift); else running = false;
    };
    window.addEventListener("mousemove", function (e) {
      tx = e.clientX / window.innerWidth - 0.5; ty = e.clientY / window.innerHeight - 0.5;
      if (!running) { running = true; requestAnimationFrame(drift); }
    }, { passive: true });
  }

  /* 換頁：站內連結先淡出 */
  if (!reduce) document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0 || a.target === "_blank") return;
    var url = new URL(a.href, location.href);
    if (url.origin !== location.origin || (url.pathname === location.pathname && url.hash)) return;
    if (!/\.html$|\/$/.test(url.pathname)) return;
    e.preventDefault();
    root.classList.add("leaving");
    setTimeout(function () { location.href = a.href; }, 140);
  });
  window.addEventListener("pageshow", function (e) { if (e.persisted) root.classList.remove("leaving"); });

  /* 燈箱：點截圖看整張 */
  var lb = document.getElementById("lb");
  if (lb) {
    var big = lb.querySelector("img"), last = null;
    var open = function (el) {
      last = el; big.src = el.currentSrc || el.src; big.alt = el.alt || "";
      lb.hidden = false; root.classList.add("lb-open"); document.body.style.overflow = "hidden";
      var t = el.getBoundingClientRect(), b = big.getBoundingClientRect();
      big.style.setProperty("--ox", (t.left + t.width / 2 - b.left) + "px");
      big.style.setProperty("--oy", (t.top + t.height / 2 - b.top) + "px");
      requestAnimationFrame(function () { lb.classList.add("show"); });
      lb.querySelector(".lb-x").focus();
    };
    var close = function () {
      lb.classList.remove("show"); root.classList.remove("lb-open"); document.body.style.overflow = "";
      setTimeout(function () { lb.hidden = true; big.removeAttribute("src"); }, 300);
      if (last) last.focus();
    };
    each(".fr img", function (el) {
      el.tabIndex = 0; el.setAttribute("role", "button");
      el.addEventListener("click", function () { open(el); });
      el.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(el); } });
    });
    lb.addEventListener("click", close);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !lb.hidden) close(); });
  }
})();
