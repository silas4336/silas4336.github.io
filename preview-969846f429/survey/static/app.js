"use strict";

const FALLBACK_CATEGORIES = [
  "1. 我覺得這個習慣/做法很具有數學邏輯",
  "2. 我受不了這些沒有數學/邏輯的行為",
  "3. 我會運用數學邏輯的思維進行什麼事?",
  "4. 如果我的數學邏輯更強一點，在【什麼事上】應該可以更如魚得水?",
  "5. 其他【我就是有話要說】",
];

const PARTICIPANT_KEY = "mathLogicSurveyParticipant";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

let configPromise = null;
let config = {
  categories: FALLBACK_CATEGORIES,
  joinUrl: `${location.href.split("#")[0]}#/join`,
  baseUrl: location.origin,
};

let toastTimer = null;
let modalCloseCallback = null;
let adminBound = false;
let adminState = {
  responses: [],
  summary: null,
};

function showToast(message) {
  const toast = $("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 2800);
}

function openModal(title, text, onClose = null) {
  modalCloseCallback = onClose;
  $("#modal-title").textContent = title;
  $("#modal-text").textContent = text;
  $("#modal").hidden = false;
  setTimeout(() => $("#modal-close").focus(), 0);
}

function closeModal(triggerCallback = true) {
  const modal = $("#modal");
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  const callback = modalCloseCallback;
  modalCloseCallback = null;
  if (triggerCallback && typeof callback === "function") {
    callback();
  }
}

async function api(path, options = {}) {
  const request = {
    method: options.method || "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  };
  if (options.body !== undefined) {
    request.headers["Content-Type"] = "application/json";
    request.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, request);
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  if (!response.ok) {
    const message = data && data.error ? data.error : `連線失敗（${response.status}）`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function loadConfig() {
  if (configPromise) return configPromise;
  configPromise = api("/api/config")
    .then((data) => {
      config = {
        ...config,
        ...data,
        categories:
          Array.isArray(data.categories) && data.categories.length
            ? data.categories
            : FALLBACK_CATEGORIES,
        joinUrl: data.joinUrl || `${location.href.split("#")[0]}#/join`,
        baseUrl: data.baseUrl || location.origin,
      };
      return config;
    })
    .catch(() => {
      showToast("無法取得活動設定，使用預設內容。");
      return config;
    });
  return configPromise;
}

function categoryName(number) {
  const index = Number(number) - 1;
  return config.categories[index] || `類別 ${number}`;
}

function formatTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function showView(id) {
  $$(".view").forEach((view) => {
    view.hidden = view.id !== id;
  });
  window.scrollTo({ top: 0, behavior: "auto" });
}

function renderQrCode(url) {
  const box = $("#qr-code");
  if (!box) return;
  box.replaceChildren();

  if (typeof window.qrcode === "function") {
    try {
      const qr = window.qrcode(0, "M");
      qr.addData(url);
      qr.make();
      box.innerHTML = qr.createSvgTag({ cellSize: 5, margin: 4, scalable: true });
      const svg = $("svg", box);
      if (svg) {
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", "參加填寫的 QR Code");
      }
      return;
    } catch (error) {
      console.error("QR Code 產生失敗", error);
    }
  }

  const fallback = document.createElement("div");
  fallback.className = "qr-placeholder";
  fallback.textContent = "QR Code 載入失敗，請使用下方連結";
  box.appendChild(fallback);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    showToast("已複製連結。");
    return;
  } catch (error) {
    // 舊瀏覽器或非 HTTPS 環境的備援。
  }

  const input = document.createElement("textarea");
  input.value = text;
  input.setAttribute("readonly", "");
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.appendChild(input);
  input.select();
  try {
    document.execCommand("copy");
    showToast("已複製連結。");
  } catch (error) {
    showToast("複製失敗，請手動選取連結。");
  } finally {
    input.remove();
  }
}

function getParticipant() {
  try {
    const value = JSON.parse(localStorage.getItem(PARTICIPANT_KEY) || "null");
    if (value && typeof value.id === "string" && typeof value.nickname === "string") {
      return value;
    }
  } catch (error) {
    // 損壞的本機資料直接忽略。
  }
  return null;
}

function saveParticipant(participant) {
  localStorage.setItem(PARTICIPANT_KEY, JSON.stringify(participant));
}

function clearParticipant() {
  localStorage.removeItem(PARTICIPANT_KEY);
}

function setJoinStep(step) {
  $("#join-nickname-step").hidden = step !== "nickname";
  $("#join-response-step").hidden = step !== "response";
  $("#join-thanks").hidden = step !== "thanks";
}

function setFormError(selector, message) {
  const element = $(selector);
  if (element) element.textContent = message || "";
}

function showJoinForm(participant) {
  $("#join-name").textContent = participant.nickname;
  setJoinStep("response");
  const textarea = $("#response-text");
  if (textarea) textarea.focus();
}

async function initHome() {
  showView("view-home");
  $("#join-url").textContent = config.joinUrl;
  renderQrCode(config.joinUrl);

  $("#copy-url").addEventListener("click", () => {
    copyText(config.joinUrl);
  });

  try {
    const summary = await api("/api/summary");
    const total = $("#watch-total");
    if (total) total.textContent = summary.totalResponses || 0;
  } catch (error) {
    // 首頁統計失敗不影響 QR Code 與填寫。
  }
}

async function initJoin() {
  showView("view-join");
  setFormError("#nickname-error", "");
  setFormError("#response-error", "");

  const nicknameForm = $("#nickname-form");
  const nicknameInput = $("#nickname");
  const responseForm = $("#response-form");
  const responseText = $("#response-text");
  const responseCount = $("#response-count");
  const maxLength = Number(responseText.getAttribute("maxlength")) || 2000;
  const updateCount = () => {
    if (!responseCount) return;
    const length = responseText.value.length;
    responseCount.textContent = `${length} / ${maxLength}`;
    responseCount.classList.toggle("near-limit", length >= maxLength * 0.9 && length < maxLength);
    responseCount.classList.toggle("at-limit", length >= maxLength);
  };
  responseText.addEventListener("input", updateCount);
  responseForm.addEventListener("reset", () => setTimeout(updateCount, 0));
  updateCount();

  const participant = getParticipant();
  if (participant) {
    showJoinForm(participant);
  } else {
    setJoinStep("nickname");
    setTimeout(() => nicknameInput.focus(), 0);
  }

  nicknameForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setFormError("#nickname-error", "");
    const nickname = nicknameInput.value.trim();
    if (!nickname) {
      setFormError("#nickname-error", "請輸入參加者暱稱。");
      nicknameInput.focus();
      return;
    }

    const submitButton = $("button[type=submit]", nicknameForm);
    submitButton.disabled = true;
    try {
      const data = await api("/api/join", {
        method: "POST",
        body: { nickname },
      });
      saveParticipant(data.participant);
      nicknameForm.reset();
      responseForm.reset();
      showJoinForm(data.participant);
      showToast("已建立參加者資料。");
    } catch (error) {
      setFormError("#nickname-error", error.message);
    } finally {
      submitButton.disabled = false;
    }
  });

  responseForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setFormError("#response-error", "");
    const current = getParticipant();
    if (!current) {
      setJoinStep("nickname");
      setFormError("#nickname-error", "請先輸入參加者暱稱。");
      return;
    }

    const checked = $('input[name="category"]:checked', responseForm);
    const category = checked ? Number(checked.value) : 0;
    const text = responseText.value.trim();

    if (!category) {
      setFormError("#response-error", "請先選擇一個類別。");
      return;
    }
    if (!text) {
      setFormError("#response-error", "請填寫你的回答。");
      responseText.focus();
      return;
    }

    const submitButton = $("#submit-response");
    const submitLabel = submitButton.dataset.label || submitButton.textContent;
    submitButton.dataset.label = submitLabel;
    let sent = false;
    submitButton.disabled = true;
    try {
      await api("/api/responses", {
        method: "POST",
        body: {
          participantId: current.id,
          category,
          text,
        },
      });
      responseForm.reset();
      responseText.value = "";
      updateCount();
      sent = true;
      submitButton.textContent = "✓ 已送出";
      submitButton.classList.add("is-done");
      showToast("已送出，可以繼續填寫下一則。");
      const firstCategory = $('input[name="category"]', responseForm);
      if (firstCategory) firstCategory.focus();
      setTimeout(() => {
        submitButton.textContent = submitLabel;
        submitButton.classList.remove("is-done");
        submitButton.disabled = false;
      }, 1400);
    } catch (error) {
      setFormError("#response-error", error.message);
    } finally {
      if (!sent) submitButton.disabled = false;
    }
  });

  $("#finish-response").addEventListener("click", async () => {
    const checked = $('input[name="category"]:checked', responseForm);
    const hasDraft = responseText.value.trim() || checked;
    if (hasDraft && !window.confirm("尚未送出的內容不會保留，確定要結束離開嗎？")) {
      return;
    }

    const current = getParticipant();
    clearParticipant();
    setJoinStep("thanks");
    if (current) {
      api("/api/finish", {
        method: "POST",
        body: { participantId: current.id },
      }).catch(() => {});
    }
  });

  $("#change-name").addEventListener("click", () => {
    const hasDraft =
      responseText.value.trim() || $('input[name="category"]:checked', responseForm);
    if (hasDraft && !window.confirm("目前未送出的內容會清除，確定要換一位參加者嗎？")) {
      return;
    }
    clearParticipant();
    responseForm.reset();
    responseText.value = "";
    setJoinStep("nickname");
    nicknameInput.focus();
  });

  $("#restart-join").addEventListener("click", () => {
    clearParticipant();
    setJoinStep("nickname");
    nicknameInput.focus();
  });
}

async function initWatchHome() {
  showView("view-watch");
  try {
    const summary = await api("/api/summary");
    $("#watch-total").textContent = summary.totalResponses || 0;
  } catch (error) {
    $("#watch-total").textContent = "0";
  }
}

function createLiveViewer(category) {
  const isCategory = Number.isInteger(category);
  const title = isCategory ? `類別觀看：${categoryName(category)}` : "即時觀看";
  $("#live-title").textContent = title;
  $("#live-subtitle").textContent = isCategory
    ? "此類別收到新回答時會自動更新；按「下一則」依序觀看。"
    : "收到新回答時會自動更新；按「下一則」依序觀看。";
  $("#live-back").href = isCategory ? "#/watch/categories" : "#/watch";

  const state = {
    responses: [],
    index: -1,
    latestSeq: 0,
    category: isCategory ? category : null,
    noDataModal: false,
    timer: null,
    loading: false,
  };

  let shownId = null;
  let shownTotal = 0;

  const renderProgress = () => {
    const progress = $("#live-progress");
    const total = state.responses.length;
    const grew = total > shownTotal && shownTotal > 0;
    shownTotal = total;
    progress.replaceChildren();
    if (!total) {
      progress.textContent = "尚無回答";
    } else {
      const count = document.createElement("span");
      count.className = "viewer-count";
      count.textContent = String(total);
      if (state.responses[state.index]) {
        progress.append(`第 ${state.index + 1} / `, count, " 則");
      } else {
        progress.append("共 ", count, " 則");
      }
      if (grew) count.classList.add("bump");
    }
    $("#live-prev").disabled = state.index <= 0;
  };

  const render = (direction = "") => {
    const content = $("#live-content");
    const empty = $("#live-empty");
    const newBadge = $("#live-new-badge");
    const response = state.responses[state.index];

    if (!response) {
      content.hidden = true;
      empty.hidden = false;
      shownId = null;
      renderProgress();
      return;
    }

    empty.hidden = true;
    content.hidden = false;
    if (direction && shownId !== null && shownId !== response.id) {
      content.classList.remove("swap-next", "swap-prev");
      void content.offsetWidth;
      content.classList.add(direction === "prev" ? "swap-prev" : "swap-next");
    }
    shownId = response.id;
    $("#live-nickname").textContent = response.nickname;
    const time = $("#live-time");
    time.textContent = formatTime(response.createdAt);
    time.setAttribute("datetime", response.createdAt || "");
    $("#live-category").textContent = categoryName(response.category);
    $("#live-text").textContent = response.text;
    renderProgress();
    if (state.index + 1 >= state.responses.length) newBadge.hidden = true;
  };

  const initialQuery = state.category ? `?category=${state.category}` : "";
  api(`/api/responses${initialQuery}`)
    .then((data) => {
      state.responses = Array.isArray(data.responses) ? data.responses : [];
      state.latestSeq = Number(data.latestSeq) || 0;
      if (state.responses.length) {
        state.index = 0;
      }
      render();
    })
    .catch((error) => {
      $("#live-status").textContent = `載入失敗：${error.message}`;
      $("#live-status").classList.add("error");
    });

  const poll = async () => {
    if (state.loading) return;
    state.loading = true;
    try {
      const params = new URLSearchParams({ after: String(state.latestSeq) });
      if (state.category) params.set("category", String(state.category));
      const data = await api(`/api/responses?${params.toString()}`);
      const incoming = Array.isArray(data.responses) ? data.responses : [];
      state.latestSeq = Math.max(state.latestSeq, Number(data.latestSeq) || 0);

      if (incoming.length) {
        const known = new Set(state.responses.map((item) => item.id));
        const fresh = incoming.filter((item) => !known.has(item.id));
        if (fresh.length) {
          state.responses.push(...fresh);
          if (state.noDataModal) {
            state.noDataModal = false;
            closeModal(false);
            if (state.index + 1 < state.responses.length) {
              state.index += 1;
            }
            render("next");
          } else if (state.index < 0) {
            state.index = 0;
            render();
          } else {
            $("#live-new-badge").hidden = false;
            renderProgress();
          }
        }
      }

      $("#live-status").textContent = "";
      $("#live-status").classList.remove("error");
    } catch (error) {
      $("#live-status").textContent = "連線中斷，正在重試…";
      $("#live-status").classList.add("error");
    } finally {
      state.loading = false;
    }
  };

  let syncing = false;
  const syncDeleted = async () => {
    if (syncing || !state.responses.length) return;
    syncing = true;
    try {
      const data = await api(`/api/responses${initialQuery}`);
      const list = Array.isArray(data.responses) ? data.responses : [];
      const alive = new Set(list.map((item) => item.id));
      const current = state.responses[state.index];
      const before = state.responses.length;
      const kept = state.responses.filter((item) => alive.has(item.id));
      if (kept.length === before) return;
      const removedBefore = state.responses
        .slice(0, Math.max(state.index, 0))
        .filter((item) => !alive.has(item.id)).length;
      state.responses = kept;
      if (!kept.length) {
        state.index = -1;
      } else if (current && alive.has(current.id)) {
        state.index -= removedBefore;
      } else {
        state.index = Math.min(Math.max(state.index - removedBefore, 0), kept.length - 1);
      }
      shownTotal = kept.length;
      render(current && alive.has(current.id) ? "" : "next");
    } catch (error) {
      // 同步失敗就等下一輪
    } finally {
      syncing = false;
    }
  };

  let pollCount = 0;
  state.timer = window.setInterval(() => {
    poll();
    pollCount += 1;
    if (pollCount % 4 === 0) syncDeleted();
  }, 3000);

  const goNext = () => {
    if (state.index + 1 < state.responses.length) {
      state.index += 1;
      render("next");
      return;
    }

    state.noDataModal = true;
    openModal("沒有新的資料", "目前沒有新的回覆。收到新資料時會自動顯示。", () => {
      state.noDataModal = false;
    });
  };

  const goPrev = () => {
    if (state.index > 0) {
      state.index -= 1;
      render("prev");
    }
  };

  $("#live-next").addEventListener("click", goNext);
  $("#live-prev").addEventListener("click", goPrev);

  // 鍵盤與簡報筆（簡報筆通常送出方向鍵或 PageUp/PageDown）
  document.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const tag = (event.target && event.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    const nextKeys = ["ArrowRight", "ArrowDown", "PageDown", " "];
    const prevKeys = ["ArrowLeft", "ArrowUp", "PageUp"];
    if (!$("#modal").hidden) {
      if (nextKeys.includes(event.key)) {
        event.preventDefault();
        closeModal(true);
      }
      return;
    }
    if (tag === "BUTTON" && event.key === " ") return;
    if (nextKeys.includes(event.key)) {
      event.preventDefault();
      goNext();
    } else if (prevKeys.includes(event.key)) {
      event.preventDefault();
      goPrev();
    }
  });

  window.addEventListener("beforeunload", () => {
    if (state.timer) window.clearInterval(state.timer);
  });
}

async function initCategories() {
  showView("view-categories");
  const grid = $("#category-grid");
  grid.replaceChildren();

  try {
    const summary = await api("/api/summary");
    config.categories.forEach((name, index) => {
      const number = index + 1;
      const count = Number(summary.categoryCounts && summary.categoryCounts[String(number)]) || 0;
      const latest = summary.latestByCategory && summary.latestByCategory[String(number)];

      const link = document.createElement("a");
      link.className = "category-card";
      link.href = `#/watch/category?cat=${number}`;

      const badge = document.createElement("span");
      badge.className = "category-number";
      badge.textContent = String(number);

      const title = document.createElement("h2");
      title.textContent = name;

      const meta = document.createElement("div");
      meta.className = "category-meta";
      const countLabel = document.createElement("span");
      countLabel.textContent = `${count} 則回答`;
      const latestLabel = document.createElement("span");
      latestLabel.textContent = latest ? `最新：${formatTime(latest)}` : "尚無回答";
      meta.append(countLabel, latestLabel);

      link.append(badge, title, meta);
      grid.appendChild(link);
    });
  } catch (error) {
    const message = document.createElement("p");
    message.className = "empty-state";
    message.textContent = `載入失敗：${error.message}`;
    grid.appendChild(message);
  }
}

function adminFilteredResponses() {
  const keyword = $("#admin-search").value.trim().toLowerCase();
  const category = $("#admin-category-filter").value;
  const onlyHighlight = $("#admin-only-highlight").checked;
  const sort = $("#admin-sort").value;

  const rows = adminState.responses.filter((response) => {
    if (category && String(response.category) !== category) return false;
    if (onlyHighlight && !response.highlight) return false;
    if (!keyword) return true;
    const haystack = [
      response.nickname,
      response.text,
      response.adminNote,
      categoryName(response.category),
    ]
      .join("\n")
      .toLowerCase();
    return haystack.includes(keyword);
  });

  rows.sort((a, b) => {
    const diff = Number(a.seq) - Number(b.seq);
    return sort === "desc" ? -diff : diff;
  });
  return rows;
}

function updateAdminExportLink() {
  const category = $("#admin-category-filter").value;
  const onlyHighlight = $("#admin-only-highlight").checked;
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (onlyHighlight) params.set("highlight", "1");
  const query = params.toString();
  $("#admin-export").href = `api/admin/export.csv${query ? `?${query}` : ""}`;
}

function renderAdminStats() {
  const summary = adminState.summary;
  const stats = $("#admin-stats");
  stats.replaceChildren();
  if (!summary) return;

  const cards = [
    ["總回答數", summary.totalResponses || 0],
    ["參加人數", summary.participants || 0],
    ["已結束", summary.finishedParticipants || 0],
    ["精選回答", summary.highlighted || 0],
  ];

  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "stat-card";
    const labelElement = document.createElement("span");
    labelElement.textContent = label;
    const valueElement = document.createElement("strong");
    valueElement.textContent = String(value);
    card.append(labelElement, valueElement);
    stats.appendChild(card);
  });
}

function renderCategoryFilter() {
  const select = $("#admin-category-filter");
  const current = select.value;
  select.replaceChildren();
  const all = document.createElement("option");
  all.value = "";
  all.textContent = "全部類別";
  select.appendChild(all);

  config.categories.forEach((name, index) => {
    const number = String(index + 1);
    const count =
      Number(adminState.summary && adminState.summary.categoryCounts && adminState.summary.categoryCounts[number]) || 0;
    const option = document.createElement("option");
    option.value = number;
    option.textContent = `${name}（${count}）`;
    select.appendChild(option);
  });
  select.value = current;
}

function makeCell(text, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text;
  return cell;
}

async function patchResponse(id, payload) {
  const data = await api(`/api/admin/responses/${id}`, {
    method: "PATCH",
    body: payload,
  });
  const index = adminState.responses.findIndex((item) => item.id === id);
  if (index >= 0) adminState.responses[index] = data.response;
  return data.response;
}

async function refreshAdminSummary() {
  try {
    adminState.summary = await api("/api/admin/summary");
    renderAdminStats();
    renderCategoryFilter();
  } catch (error) {
    if (error.status === 401) {
      showAdminAuth(false);
      throw error;
    }
    showToast(`統計更新失敗：${error.message}`);
  }
}

function renderAdminRows() {
  const tbody = $("#admin-tbody");
  tbody.replaceChildren();
  const rows = adminFilteredResponses();
  const empty = $("#admin-empty");
  empty.hidden = rows.length > 0;
  updateAdminExportLink();

  if (!rows.length) {
    return;
  }

  rows.forEach((response) => {
    const tr = document.createElement("tr");

    tr.appendChild(makeCell(String(response.seq || ""), "cell-seq"));
    tr.appendChild(makeCell(response.nickname || "", "cell-nickname"));
    tr.appendChild(makeCell(categoryName(response.category), "cell-category"));
    tr.appendChild(makeCell(response.text || "", "cell-content"));

    const timeCell = document.createElement("td");
    timeCell.className = "cell-time";
    const time = document.createElement("time");
    time.textContent = formatTime(response.createdAt);
    time.setAttribute("datetime", response.createdAt || "");
    timeCell.appendChild(time);
    tr.appendChild(timeCell);

    const highlightCell = document.createElement("td");
    highlightCell.className = "cell-highlight";
    const highlight = document.createElement("input");
    highlight.type = "checkbox";
    highlight.checked = Boolean(response.highlight);
    highlight.setAttribute("aria-label", `標記 ${response.nickname} 的回答為精選`);
    highlight.addEventListener("change", async () => {
      highlight.disabled = true;
      try {
        await patchResponse(response.id, { highlight: highlight.checked });
        await refreshAdminSummary();
        if ($("#admin-only-highlight").checked && !highlight.checked) {
          renderAdminRows();
        }
        if (!$("#admin-curated").hidden) renderCurated();
        showToast(highlight.checked ? "已標記為精選。" : "已取消精選。");
      } catch (error) {
        highlight.checked = !highlight.checked;
        if (error.status === 401) {
          showAdminAuth(false);
          showToast("登入已過期，請重新登入。");
        } else {
          showToast(`更新失敗：${error.message}`);
        }
      } finally {
        highlight.disabled = false;
      }
    });
    highlightCell.appendChild(highlight);
    tr.appendChild(highlightCell);

    const noteCell = document.createElement("td");
    const noteBox = document.createElement("div");
    noteBox.className = "note-box";
    const noteInput = document.createElement("textarea");
    noteInput.value = response.adminNote || "";
    noteInput.maxLength = 2000;
    noteInput.placeholder = "新增整理備註…";
    noteInput.setAttribute("aria-label", `給 ${response.nickname} 的後台備註`);
    const saveNote = document.createElement("button");
    saveNote.type = "button";
    saveNote.className = "note-save";
    saveNote.textContent = "儲存備註";
    saveNote.addEventListener("click", async () => {
      saveNote.disabled = true;
      try {
        await patchResponse(response.id, { adminNote: noteInput.value });
        if (!$("#admin-curated").hidden) renderCurated();
        showToast("備註已儲存。");
      } catch (error) {
        if (error.status === 401) {
          showAdminAuth(false);
          showToast("登入已過期，請重新登入。");
        } else {
          showToast(`儲存失敗：${error.message}`);
        }
      } finally {
        saveNote.disabled = false;
      }
    });
    noteBox.append(noteInput, saveNote);
    noteCell.appendChild(noteBox);
    tr.appendChild(noteCell);

    const actionCell = document.createElement("td");
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-btn";
    deleteButton.textContent = "刪除";
    deleteButton.addEventListener("click", async () => {
      if (!window.confirm(`確定要刪除 ${response.nickname} 的這則回答嗎？`)) return;
      deleteButton.disabled = true;
      try {
        await api(`/api/admin/responses/${response.id}`, { method: "DELETE" });
        adminState.responses = adminState.responses.filter((item) => item.id !== response.id);
        await refreshAdminSummary();
        renderAdminRows();
        if (!$("#admin-curated").hidden) renderCurated();
        showToast("已刪除回答。");
      } catch (error) {
        deleteButton.disabled = false;
        if (error.status === 401) {
          showAdminAuth(false);
          showToast("登入已過期，請重新登入。");
        } else {
          showToast(`刪除失敗：${error.message}`);
        }
      }
    });
    actionCell.appendChild(deleteButton);
    tr.appendChild(actionCell);

    tbody.appendChild(tr);
  });
}

function renderCurated() {
  const container = $("#admin-curated-content");
  container.replaceChildren();
  const selected = adminState.responses
    .filter((response) => response.highlight)
    .sort((a, b) => Number(a.seq) - Number(b.seq));

  if (!selected.length) {
    const empty = document.createElement("p");
    empty.className = "curated-empty";
    empty.textContent = "尚未標記精選回答。請在下方表格勾選「精選」後再回來彙整。";
    container.appendChild(empty);
    return;
  }

  config.categories.forEach((name, index) => {
    const number = index + 1;
    const rows = selected.filter((response) => Number(response.category) === number);
    if (!rows.length) return;

    const group = document.createElement("section");
    group.className = "curated-group";
    const heading = document.createElement("h3");
    heading.textContent = name;
    group.appendChild(heading);

    rows.forEach((response) => {
      const item = document.createElement("article");
      item.className = "curated-item";

      const meta = document.createElement("div");
      meta.className = "curated-meta";
      const who = document.createElement("strong");
      who.textContent = response.nickname || "未命名參加者";
      const when = document.createElement("span");
      when.textContent = formatTime(response.createdAt);
      meta.append(who, when);

      const text = document.createElement("p");
      text.textContent = response.text || "";

      item.append(meta, text);
      if (response.adminNote) {
        const note = document.createElement("p");
        note.className = "curated-note";
        note.textContent = `備註：${response.adminNote}`;
        item.appendChild(note);
      }
      group.appendChild(item);
    });

    container.appendChild(group);
  });
}

function showAdminAuth(authenticated) {
  $("#admin-login").hidden = authenticated;
  $("#admin-content").hidden = !authenticated;
  $("#admin-logout").hidden = !authenticated;
  if (!authenticated) {
    adminState.responses = [];
    adminState.summary = null;
    $("#admin-password").value = "";
    setFormError("#admin-login-error", "");
    setTimeout(() => $("#admin-password").focus(), 0);
  }
}

async function checkAdminSession() {
  try {
    const data = await api("/api/admin/session");
    return Boolean(data.authenticated);
  } catch (error) {
    return false;
  }
}

async function loadAdmin() {
  const refreshButton = $("#admin-refresh");
  refreshButton.disabled = true;
  try {
    const [data] = await Promise.all([
      api("/api/admin/responses"),
      refreshAdminSummary(),
    ]);
    adminState.responses = Array.isArray(data.responses) ? data.responses : [];
    renderAdminRows();
    if (!$("#admin-curated").hidden) renderCurated();
  } catch (error) {
    if (error.status === 401) {
      showAdminAuth(false);
      showToast("請先登入後台。");
    } else {
      showToast(`載入失敗：${error.message}`);
    }
  } finally {
    refreshButton.disabled = false;
  }
}

function downloadExport(event) {
  event.preventDefault();
  const link = $("#admin-export");
  const filename = "回答資料.csv";

  fetch(link.href, { credentials: "same-origin" })
    .then(async (response) => {
      if (response.status === 401) {
        showAdminAuth(false);
        showToast("登入已過期，請重新登入。");
        return null;
      }
      if (!response.ok) {
        throw new Error(`匯出失敗（${response.status}）`);
      }
      return response.blob();
    })
    .then((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      showToast("CSV 已開始下載。");
    })
    .catch((error) => {
      showToast(error.message);
    });
}

async function initAdmin() {
  showView("view-admin");

  if (!adminBound) {
    adminBound = true;
    $("#admin-search").addEventListener("input", renderAdminRows);
    $("#admin-category-filter").addEventListener("change", renderAdminRows);
    $("#admin-sort").addEventListener("change", renderAdminRows);
    $("#admin-only-highlight").addEventListener("change", renderAdminRows);
    $("#admin-refresh").addEventListener("click", loadAdmin);
    $("#admin-export").addEventListener("click", downloadExport);
    $("#admin-curated-btn").addEventListener("click", () => {
      $("#admin-curated").hidden = false;
      renderCurated();
      $("#admin-curated").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("#admin-curated-close").addEventListener("click", () => {
      $("#admin-curated").hidden = true;
    });
    $("#admin-print").addEventListener("click", () => {
      window.print();
    });
    $("#admin-login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      setFormError("#admin-login-error", "");
      const password = $("#admin-password").value;
      if (!password) {
        setFormError("#admin-login-error", "請輸入後台密碼。");
        $("#admin-password").focus();
        return;
      }
      const submitButton = $("#admin-login-submit");
      submitButton.disabled = true;
      try {
        await api("/api/admin/login", {
          method: "POST",
          body: { password },
        });
        showAdminAuth(true);
        await loadAdmin();
        showToast("已登入後台。");
      } catch (error) {
        setFormError("#admin-login-error", error.message);
      } finally {
        submitButton.disabled = false;
      }
    });
    $("#admin-logout").addEventListener("click", async () => {
      try {
        await api("/api/admin/logout", { method: "POST" });
      } catch (error) {
        // 即使連線失敗，也先清除本頁狀態。
      }
      showAdminAuth(false);
      showToast("已登出後台。");
    });
  }

  const authenticated = await checkAdminSession();
  showAdminAuth(authenticated);
  if (authenticated) {
    await loadAdmin();
  }
}

async function boot() {
  $("#modal-close").addEventListener("click", () => closeModal(true));
  $("#modal").addEventListener("click", (event) => {
    if (event.target === $("#modal")) closeModal(true);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#modal").hidden) closeModal(true);
  });

  await loadConfig();

  const hashRoute = (location.hash.replace(/^#/, "") || "/").split("?");
  const path = hashRoute[0].replace(/\/+$/, "") || "/";
  window.addEventListener("hashchange", () => location.reload());
  if (path === "/join") {
    await initJoin();
  } else if (path === "/watch") {
    await initWatchHome();
  } else if (path === "/watch/live") {
    showView("view-live");
    createLiveViewer(null);
  } else if (path === "/watch/categories") {
    await initCategories();
  } else if (path === "/watch/category") {
    const category = Number(new URLSearchParams(hashRoute[1] || "").get("cat"));
    if (!Number.isInteger(category) || category < 1 || category > config.categories.length) {
      location.replace("#/watch/categories");
      return;
    }
    showView("view-live");
    createLiveViewer(category);
  } else if (path === "/admin") {
    await initAdmin();
  } else {
    await initHome();
  }
}

boot().catch((error) => {
  console.error(error);
  showToast("頁面載入失敗，請重新整理。");
});
