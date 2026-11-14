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

/* Mobile menu toggle. */
const navBurger = document.getElementById("navBurger");
const navLinks = document.getElementById("navLinks");
if (navBurger && navLinks) {
  navBurger.addEventListener("click", () => {
    const open = navLinks.classList.toggle("open");
    navBurger.setAttribute("aria-expanded", String(open));
  });
  navLinks.addEventListener("click", (ev) => {
    if (ev.target.closest("a, button")) navLinks.classList.remove("open");
  });
}

/* ---------- visual helpers --------------------------------------------- */

const AVATAR_CLASSES = ["av-0", "av-1", "av-2", "av-3", "av-4", "av-5"];

/** Deterministic initials avatar: same name -> same color, every visit. */
function avatarFor(name, size) {
  const text = (name || "?").trim().toUpperCase();
  const parts = text.split(/\s+/).filter(Boolean);
  const initials = parts.length >= 2 ? parts[0][0] + parts[1][0] : text.slice(0, 2) || "?";
  let hash = 0;
  for (const ch of text) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return el("span", `avatar ${size || ""} ${AVATAR_CLASSES[hash % AVATAR_CLASSES.length]}`, initials);
}

/** Friendly empty-state box used by the list renderers. */
function emptyState(message, { compact = false, icon = "calendar" } = {}) {
  const icons = {
    calendar:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="16" rx="3" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M8 3v4M16 3v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    users:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="9" cy="8" r="3.5" stroke="currentColor" stroke-width="2"/><path d="M2.5 19c1.4-2.9 3.7-4.5 6.5-4.5s5.1 1.6 6.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="17" cy="9" r="2.5" stroke="currentColor" stroke-width="2"/><path d="M16 14.7c2.4.2 4.2 1.5 5.3 3.8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  };
  const box = el("div", `empty${compact ? " compact" : ""}`);
  const holder = el("span", "e-icon");
  holder.innerHTML = icons[icon] || icons.calendar;
  box.append(holder, el("span", null, message));
  return box;
}

/** Wrap a trusted inline-SVG icon string (never user input) in a span. */
function iconEl(svgMarkup) {
  const node = el("span", null);
  node.innerHTML = svgMarkup;
  return node;
}

/** Add a "Dr." honorific only when the name does not already have one. */
function doctorLabel(name) {
  return /^dr[\.\s]/i.test((name || "").trim()) ? name : `Dr. ${name}`;
}
