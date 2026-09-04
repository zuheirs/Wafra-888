// وفرة 888 — منطق لوحة القيادة
(function () {
  "use strict";

  const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]').content;

  async function api(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = CSRF_TOKEN;
    const res = await fetch(path, Object.assign({}, options, { headers }));
    let data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) throw new Error((data && data.error) || `صار خطأ (${res.status})`);
    return data;
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
  }

  function fmtDate(iso) {
    if (!iso) return "";
    try { return new Date(iso).toLocaleDateString("ar", { day: "numeric", month: "short" }); }
    catch (e) { return iso; }
  }

  const STATUS_LABELS = {
    present: "حاضر", absent_excused: "غياب باعتذار", absent_unexcused: "غياب بدون اعتذار",
    left_early: "غادر بدري", frequent_excuse: "كثّر الأعذار",
  };
  const ACCOUNT_STATUS_LABELS = {
    active: "فعّال", locked_pending_review: "مقفول — بانتظار قرار", frozen: "مجمّد", deleted: "محذوف",
  };

  // ---------------- Notifications ----------------
  async function loadNotifications() {
    const listEl = document.getElementById("notifications-list");
    const emptyEl = document.getElementById("notifications-empty");
    listEl.innerHTML = "";
    const data = await api("/api/leadership/notifications?unread=1");
    if (!data.notifications.length) { emptyEl.style.display = "block"; return; }
    emptyEl.style.display = "none";
    data.notifications.forEach((n) => {
      const div = document.createElement("div");
      div.className = "flag-item";
      div.innerHTML = `${escapeHtml(n.message)} <span style="color:var(--sand-dim);font-size:11px;">(${fmtDate(n.created_at)})</span>
        <div><span class="badge" data-id="${n.id}" style="cursor:pointer;">تمييز كمقروء</span></div>`;
      div.querySelector("[data-id]").addEventListener("click", async (e) => {
        await api(`/api/leadership/notifications/${n.id}/read`, { method: "POST" });
        loadNotifications();
      });
      listEl.appendChild(div);
    });
  }
  document.getElementById("refresh-notifications").addEventListener("click", loadNotifications);

  // ---------------- Members / profiles ----------------
  async function loadLeadershipBoard() {
    const listEl = document.getElementById("leadership-list");
    const emptyEl = document.getElementById("leadership-empty");
    listEl.innerHTML = "";
    const data = await api("/api/leadership/profiles");
    if (!data.profiles.length) { emptyEl.style.display = "block"; return; }
    emptyEl.style.display = "none";
    data.profiles.forEach((rec) => {
      const div = document.createElement("div");
      div.className = "member";
      div.innerHTML = `<div class="member-top">
          <span class="member-name">${escapeHtml(rec.name)}</span>
          <span class="member-date">${fmtDate(rec.updated_at)} · ${ACCOUNT_STATUS_LABELS[rec.status] || rec.status}</span>
        </div>
        <div class="member-row"><b>DCA:</b> ${escapeHtml(rec.dca)}</div>
        <div class="member-row"><b>هدف 4 أشهر:</b> ${escapeHtml(rec.goal4m)}</div>`;
      listEl.appendChild(div);
    });
  }
  document.getElementById("refresh-leadership").addEventListener("click", loadLeadershipBoard);

  // ---------------- DCA requests ----------------
  async function loadRequests() {
    const listEl = document.getElementById("requests-list");
    const emptyEl = document.getElementById("requests-empty");
    listEl.innerHTML = "";
    const data = await api("/api/leadership/requests?status=pending");
    if (!data.requests.length) { emptyEl.style.display = "block"; return; }
    emptyEl.style.display = "none";
    data.requests.forEach((req) => {
      const div = document.createElement("div");
      div.className = "flag-item";
      div.innerHTML = `<b>${escapeHtml(req.name)}</b> — ${fmtDate(req.created_at)}<br>
        الحالي: ${escapeHtml(req.current_dca)}<br>المطلوب: ${escapeHtml(req.requested_dca)}
        <div class="row" style="margin-top:8px;">
          <button type="button" class="small" data-action="approve">موافقة</button>
          <button type="button" class="small ghost" data-action="reject">رفض</button>
        </div>`;
      div.querySelector('[data-action="approve"]').addEventListener("click", async () => {
        await api(`/api/leadership/requests/${req.id}/decide`, { method: "POST", body: JSON.stringify({ approve: true }) });
        loadRequests(); loadLeadershipBoard();
      });
      div.querySelector('[data-action="reject"]').addEventListener("click", async () => {
        await api(`/api/leadership/requests/${req.id}/decide`, { method: "POST", body: JSON.stringify({ approve: false }) });
        loadRequests();
      });
      listEl.appendChild(div);
    });
  }

  // ---------------- Patterns ----------------
  async function loadPatterns() {
    const listEl = document.getElementById("patterns-list");
    const emptyEl = document.getElementById("patterns-empty");
    listEl.innerHTML = "";
    const data = await api("/api/leadership/patterns");
    if (!data.patterns.length) { emptyEl.style.display = "block"; return; }
    emptyEl.style.display = "none";
    data.patterns.forEach((rec) => {
      const div = document.createElement("div");
      div.className = "member";
      const notesHtml = rec.notes.map((n) =>
        `<div class="member-row">• ${escapeHtml(n.text)} <span style="color:var(--sand-dim);font-size:11px;">(${fmtDate(n.created_at)})</span></div>`
      ).join("");
      div.innerHTML = `<div class="member-top"><span class="member-name">${escapeHtml(rec.name)}</span></div>${notesHtml}`;
      listEl.appendChild(div);
    });
  }

  // ---------------- Flagged accounts (locked / frozen) ----------------
  async function loadFlagged() {
    const listEl = document.getElementById("flagged-list");
    const emptyEl = document.getElementById("flagged-empty");
    listEl.innerHTML = "";
    const data = await api("/api/leadership/accounts/flagged");
    if (!data.accounts.length) { emptyEl.style.display = "block"; return; }
    emptyEl.style.display = "none";
    data.accounts.forEach((acc) => {
      const div = document.createElement("div");
      div.className = "flag-item";
      div.innerHTML = `<b>${escapeHtml(acc.name)}</b> — ${ACCOUNT_STATUS_LABELS[acc.status] || acc.status}
        ${acc.status_note ? `<br>${escapeHtml(acc.status_note)}` : ""}
        <div class="row" style="margin-top:8px;">
          <button type="button" class="small" data-action="reactivate">إرجاع طبيعي</button>
          <input type="date" class="freeze-until" style="max-width:130px;">
          <button type="button" class="small ghost" data-action="freeze">تجميد</button>
          <button type="button" class="small danger" data-action="delete">حذف نهائي</button>
        </div>`;
      const resolve = async (decision, extra) => {
        if (decision === "delete" && !confirm(`متأكد بدك تحذف حساب ${acc.name} نهائياً؟`)) return;
        await api(`/api/leadership/accounts/${acc.id}/resolve`, {
          method: "POST",
          body: JSON.stringify(Object.assign({ decision }, extra || {})),
        });
        loadFlagged();
      };
      div.querySelector('[data-action="reactivate"]').addEventListener("click", () => resolve("reactivate"));
      div.querySelector('[data-action="delete"]').addEventListener("click", () => resolve("delete"));
      div.querySelector('[data-action="freeze"]').addEventListener("click", () => {
        const until = div.querySelector(".freeze-until").value || null;
        resolve("freeze", { freeze_until: until });
      });
      listEl.appendChild(div);
    });
  }

  // ---------------- Reminders ----------------
  async function loadReminders() {
    const listEl = document.getElementById("reminders-list");
    const emptyEl = document.getElementById("reminders-empty");
    listEl.innerHTML = "";
    const data = await api("/api/leadership/reminders");
    if (!data.reminders.length) { emptyEl.style.display = "block"; return; }
    emptyEl.style.display = "none";
    data.reminders.forEach((r) => {
      const div = document.createElement("div");
      div.className = "flag-item";
      div.innerHTML = `<b>${escapeHtml(r.name)}</b> — ${escapeHtml(r.reason)}<br>
        ${r.wa_link ? `<a class="wa-link" target="_blank" rel="noopener" href="${r.wa_link}">فتح واتساب</a>` : `<span class="hint">ما في رقم هاتف مسجّل. </span>
        <input type="tel" placeholder="رقم الهاتف (مع رمز الدولة، بدون +)" class="phone-input" style="max-width:220px;display:inline-block;">
        <button type="button" class="small ghost" data-action="save-phone">حفظ الرقم</button>`}`;
      const saveBtn = div.querySelector('[data-action="save-phone"]');
      if (saveBtn) {
        saveBtn.addEventListener("click", async () => {
          const phone = div.querySelector(".phone-input").value.trim();
          if (!phone) return;
          await api(`/api/leadership/members/${r.account_id}/phone`, { method: "POST", body: JSON.stringify({ phone }) });
          loadReminders();
        });
      }
      listEl.appendChild(div);
    });
  }

  // ---------------- Meetings & attendance ----------------
  let allMembersCache = [];
  let currentMeetingId = null;

  async function loadMeetingsSelect() {
    const select = document.getElementById("meeting-select");
    const data = await api("/api/leadership/meetings");
    select.innerHTML = "";
    if (!data.meetings.length) {
      select.innerHTML = '<option value="">لا يوجد اجتماعات مسجّلة بعد</option>';
      document.getElementById("attendance-list").innerHTML = "";
      document.getElementById("save-attendance-btn").style.display = "none";
      return;
    }
    data.meetings.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.meeting_date + (m.notes ? " — " + m.notes : "");
      select.appendChild(opt);
    });
    select.value = data.meetings[0].id;
    await loadAttendanceFor(select.value);
  }

  async function loadAttendanceFor(meetingId) {
    if (!meetingId) return;
    currentMeetingId = meetingId;
    const data = await api(`/api/leadership/meetings/${meetingId}/attendance`);
    allMembersCache = data.attendance;
    const listEl = document.getElementById("attendance-list");
    listEl.innerHTML = "";
    data.attendance.forEach((row) => {
      const div = document.createElement("div");
      div.className = "member-simple";
      const options = Object.keys(STATUS_LABELS).map(
        (k) => `<option value="${k}" ${row.status === k ? "selected" : ""}>${STATUS_LABELS[k]}</option>`
      ).join("");
      div.innerHTML = `<span>${escapeHtml(row.name)}</span>
        <select class="status-select" data-account="${row.account_id}">
          <option value="">— اختر —</option>${options}
        </select>`;
      listEl.appendChild(div);
    });
    document.getElementById("save-attendance-btn").style.display = "block";
  }

  document.getElementById("meeting-select").addEventListener("change", (e) => loadAttendanceFor(e.target.value));

  document.getElementById("create-meeting-btn").addEventListener("click", async () => {
    const dateInput = document.getElementById("new-meeting-date");
    const notesInput = document.getElementById("new-meeting-notes");
    if (!dateInput.value) { alert("لازم تحدد تاريخ الاجتماع"); return; }
    await api("/api/leadership/meetings", {
      method: "POST",
      body: JSON.stringify({ meeting_date: dateInput.value, notes: notesInput.value.trim() }),
    });
    dateInput.value = ""; notesInput.value = "";
    await loadMeetingsSelect();
  });

  document.getElementById("save-attendance-btn").addEventListener("click", async () => {
    if (!currentMeetingId) return;
    const records = [];
    document.querySelectorAll("#attendance-list .status-select").forEach((sel) => {
      if (sel.value) records.push({ account_id: parseInt(sel.dataset.account, 10), status: sel.value });
    });
    await api(`/api/leadership/meetings/${currentMeetingId}/attendance`, {
      method: "POST",
      body: JSON.stringify({ records }),
    });
    alert("تم حفظ الحضور. الحسابات يلي انسجلت 'غياب بدون اعتذار' انقفلت تلقائياً وبانتظار قرارك بقسم الحسابات المعلّقة.");
    loadFlagged();
    loadNotifications();
  });

  // ---------------- AI report ----------------
  document.getElementById("report-btn").addEventListener("click", async () => {
    const spinner = document.getElementById("report-spinner");
    const box = document.getElementById("report-box");
    spinner.classList.add("visible");
    box.classList.remove("visible");
    try {
      const data = await api("/api/leadership/report", { method: "POST" });
      box.textContent = data.report || "ما قدرت أولّد تقرير هلق.";
    } catch (e) {
      box.textContent = "⚠️ " + e.message;
    }
    box.classList.add("visible");
    spinner.classList.remove("visible");
  });

  // ---------------- Leadership free chat ----------------
  let leaderChatHistory = [];
  function renderLeaderChat() {
    const log = document.getElementById("leader-chat-log");
    log.innerHTML = "";
    leaderChatHistory.forEach((m) => {
      const div = document.createElement("div");
      div.className = "msg " + (m.role === "user" ? "user" : "assistant");
      div.textContent = m.content;
      log.appendChild(div);
    });
    log.scrollTop = log.scrollHeight;
  }
  async function loadLeaderChatHistory() {
    const data = await api("/api/leadership/chat/history");
    leaderChatHistory = data.messages || [];
    renderLeaderChat();
  }
  document.getElementById("leader-chat-send").addEventListener("click", async () => {
    const input = document.getElementById("leader-chat-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    leaderChatHistory.push({ role: "user", content: text });
    renderLeaderChat();
    try {
      const data = await api("/api/leadership/chat/send", { method: "POST", body: JSON.stringify({ text }) });
      leaderChatHistory.push({ role: "assistant", content: data.reply });
    } catch (e) {
      leaderChatHistory.push({ role: "assistant", content: "⚠️ " + e.message });
    }
    renderLeaderChat();
  });

  // ---------------- entrypoint ----------------
  let loadedOnce = false;
  async function onShow() {
    try {
      await Promise.all([
        loadNotifications(), loadLeadershipBoard(), loadRequests(), loadPatterns(),
        loadFlagged(), loadReminders(), loadMeetingsSelect(),
      ]);
      if (!loadedOnce) { loadLeaderChatHistory(); loadedOnce = true; }
    } catch (e) { console.error(e); }
  }

  window.wafraLeadership = { onShow };
})();
