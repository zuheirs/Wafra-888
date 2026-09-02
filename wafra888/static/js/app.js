// وفرة 888 — منطق واجهة العضو (بروفايل / محادثة خاصة / لوحة الأعضاء)
(function () {
  "use strict";

  const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]').content;

  async function api(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = CSRF_TOKEN;
    const res = await fetch(path, Object.assign({}, options, { headers }));
    let data = null;
    try { data = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      const msg = (data && data.error) || `صار خطأ (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
  }

  // ---------------- Tabs ----------------
  function attachTabHandlers() {
    document.querySelectorAll(".tab").forEach((t) => {
      t.onclick = () => {
        document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
        t.classList.add("active");
        document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
        const panel = document.getElementById("panel-" + t.dataset.tab);
        if (panel) panel.classList.add("active");
        if (t.dataset.tab === "board") loadBoard();
        if (t.dataset.tab === "leadership" && window.wafraLeadership) window.wafraLeadership.onShow();
      };
    });
  }

  // ---------------- Profile ----------------
  const profileFieldIds = ["dca", "goal4m", "fear", "give", "want", "patterns"];

  async function loadProfile() {
    try {
      const data = await api("/api/profile");
      const p = data.profile;
      if (p) {
        profileFieldIds.forEach((f) => { document.getElementById("f-" + f).value = p[f] || ""; });
        document.getElementById("f-agree").checked = !!p.agreed;
      }
    } catch (e) { console.error(e); }
  }

  document.getElementById("submit-btn").addEventListener("click", async () => {
    const errEl = document.getElementById("profile-error");
    errEl.classList.remove("visible");
    const payload = {};
    profileFieldIds.forEach((f) => { payload[f] = document.getElementById("f-" + f).value.trim(); });
    payload.agreed = document.getElementById("f-agree").checked;

    if (Object.keys(payload).some((k) => k !== "agreed" && !payload[k]) || !payload.agreed) {
      errEl.classList.add("visible");
      return;
    }
    try {
      await api("/api/profile", { method: "POST", body: JSON.stringify(payload) });
      const s = document.getElementById("save-status");
      s.style.display = "block";
      setTimeout(() => (s.style.display = "none"), 2500);
    } catch (e) {
      errEl.textContent = e.message;
      errEl.classList.add("visible");
    }
  });

  // ---------------- Board ----------------
  async function loadBoard() {
    const listEl = document.getElementById("board-list");
    const emptyEl = document.getElementById("board-empty");
    listEl.innerHTML = "";
    try {
      const data = await api("/api/board");
      if (!data.members.length) { emptyEl.style.display = "block"; return; }
      emptyEl.style.display = "none";
      data.members.forEach((m) => {
        const div = document.createElement("div");
        div.className = "member-simple";
        const dateStr = m.submitted_at ? new Date(m.submitted_at).toLocaleDateString("ar", { day: "numeric", month: "short" }) : "";
        const badge = m.submitted
          ? `<span class="badge">✓ قدّم الفورم — ${dateStr}</span>`
          : `<span class="badge pending">لسا ما قدّم الفورم</span>`;
        div.innerHTML = `<span>${escapeHtml(m.name)}</span>${badge}`;
        listEl.appendChild(div);
      });
    } catch (e) {
      emptyEl.textContent = "تعذّر تحميل القائمة.";
      emptyEl.style.display = "block";
    }
  }
  document.getElementById("refresh-board").addEventListener("click", loadBoard);

  // ---------------- Chat ----------------
  let chatHistory = [];

  function renderChatLog() {
    const log = document.getElementById("chat-log");
    log.innerHTML = "";
    chatHistory.forEach((m) => {
      const div = document.createElement("div");
      div.className = "msg " + (m.role === "user" ? "user" : "assistant");
      div.textContent = m.content;
      log.appendChild(div);
    });
    log.scrollTop = log.scrollHeight;
  }

  async function loadChatHistory() {
    try {
      const data = await api("/api/chat/history");
      chatHistory = data.messages || [];
      renderChatLog();
    } catch (e) { console.error(e); }
  }

  const chatInput = document.getElementById("chat-input");
  const chatSendBtn = document.getElementById("chat-send-btn");

  async function sendChat() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    chatHistory.push({ role: "user", content: text });
    renderChatLog();
    chatSendBtn.disabled = true;
    try {
      const data = await api("/api/chat/send", { method: "POST", body: JSON.stringify({ text }) });
      chatHistory.push({ role: "assistant", content: data.reply });
      renderChatLog();
      if (data.dca_request_created) {
        chatHistory.push({ role: "assistant", content: "📩 تم إرسال طلب تغيير الـ DCA للقيادة للموافقة." });
        renderChatLog();
      }
    } catch (e) {
      chatHistory.push({ role: "assistant", content: "⚠️ " + e.message });
      renderChatLog();
    } finally {
      chatSendBtn.disabled = false;
    }
  }
  chatSendBtn.addEventListener("click", sendChat);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  // ---------------- Voice-to-text (Web Speech API) ----------------
  (function setupVoice() {
    const micBtn = document.getElementById("mic-btn");
    const hint = document.getElementById("mic-hint");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      micBtn.disabled = true;
      micBtn.title = "التسجيل الصوتي مو مدعوم بهالمتصفح";
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "ar-SA";
    recognition.interimResults = true;
    recognition.continuous = false;
    let recording = false;

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) transcript += event.results[i][0].transcript;
      chatInput.value = transcript;
    };
    recognition.onerror = (event) => {
      hint.style.display = "block";
      hint.textContent = "صار خطأ بالتسجيل الصوتي (" + event.error + "). جرّب تكتب عادي.";
    };
    recognition.onend = () => {
      recording = false;
      micBtn.classList.remove("recording");
    };

    micBtn.addEventListener("click", () => {
      if (recording) { recognition.stop(); return; }
      hint.style.display = "none";
      try {
        recognition.start();
        recording = true;
        micBtn.classList.add("recording");
      } catch (e) {
        hint.style.display = "block";
        hint.textContent = "ما قدرنا نبدأ التسجيل. جرّب كمان مرة.";
      }
    });
  })();

  // ---------------- init ----------------
  attachTabHandlers();
  loadProfile();
  loadChatHistory();
})();
