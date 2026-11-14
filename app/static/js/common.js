/* Shared helpers for all pages. */
"use strict";

/** Fetch JSON and return {ok, status, data}. Session cookies sent automatically. */
async function api(url, { method = "GET", body } = {}) {
  const res = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  return { ok: res.ok, status: res.status, data };
}

/** "2026-11-20T09:00:00Z" -> "Thu, Nov 20 · 09:00–09:30" in the viewer's timezone. */
function formatSlot(slot) {
  const start = new Date(slot.start_time);
  const end = new Date(slot.end_time);
  const day = start.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const time = `${fmtTime(start)}–${fmtTime(end)}`;
  return `${day} · ${time}`;
}

function fmtTime(d) {
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text; // safe against HTML injection
  return node;
}

function showError(node, message) {
  node.textContent = message;
  node.hidden = false;
}

function clearError(node) {
  node.hidden = true;
  node.textContent = "";
}

/* Wire the navbar logout button if present. */
const logoutBtn = document.getElementById("logoutBtn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    window.location.href = "/";
  });
}
