/* Dashboard: appointments (both roles) + slot management (doctors). */
"use strict";

const socket = io();
const appointmentList = document.getElementById("appointmentList");
const slotManager = document.getElementById("slotManager");

let me = null;

async function init() {
  const { ok, data } = await api("/api/auth/me");
  if (!ok) {
    window.location.href = "/login?next=/dashboard";
    return;
  }
  me = data.user;

  document.getElementById("welcomeTitle").textContent =
    me.role === "doctor" ? doctorLabel(me.full_name) : `Welcome, ${me.full_name}`;

  if (me.role === "doctor") {
    slotManager.hidden = false;
    initSlotManager();
    socket.on("connect", () => socket.emit("subscribe_doctor", { doctor_id: me.id }));
    socket.on("slot_update", async (slot) => {
      // Patients see bookings live: a slot just got taken or freed.
      await Promise.all([loadMySlots(), loadAppointments()]);
    });
  }

  await loadAppointments();
}

/* ---------- appointments ------------------------------------------------- */
async function loadAppointments() {
  const { ok, data } = await api("/api/appointments");
  if (!ok) {
    appointmentList.replaceChildren(el("p", "muted", "Could not load appointments."));
    return;
  }
  if (!data.appointments.length) {
    appointmentList.replaceChildren(
      emptyState("No appointments yet. Use “Book a new appointment” to get started."),
    );
    return;
  }

  const CAL_ICON =
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="16" rx="3" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M8 3v4M16 3v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  const NOTE_ICON =
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M5 4h14v16l-3-2-3 2-3-2-3 2V4z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M9 9h6M9 12h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';

  const cards = data.appointments.map((a) => {
    const card = el("article", "card appointment-card");

    const head = el("div", "appointment-head");
    const otherName = me.role === "doctor" ? a.patient.full_name : doctorLabel(a.doctor.full_name);
    head.append(avatarFor(otherName, "avatar-sm"));
    head.append(el("span", "a-name", otherName));
    head.append(el("span", `badge badge-${a.status}`, a.status));

    const meta = el("div", "appointment-meta");
    const when = el("span", "a-line");
    when.append(iconEl(CAL_ICON), el("span", null, a.slot ? formatSlot(a.slot) : "No slot attached"));
    meta.append(when);
    if (a.symptoms) {
      const note = el("span", "a-line a-note");
      note.append(iconEl(NOTE_ICON), el("span", null, `Symptoms: ${a.symptoms}`));
      meta.append(note);
    }

    card.append(head, meta);

    const actions = el("div", "appointment-actions");
    if (a.status === "scheduled") {
      const chat = el("a", "btn btn-primary btn-sm", "Chat");
      chat.href = `/chat/${a.id}`;
      actions.append(chat);

      const cancel = el("button", "btn btn-danger btn-sm", "Cancel");
      cancel.type = "button";
      cancel.addEventListener("click", async () => {
        if (!window.confirm("Cancel this appointment?")) return;
        const res = await api(`/api/appointments/${a.id}/cancel`, { method: "POST" });
        if (!res.ok) window.alert(res.data.error || "Could not cancel.");
        await loadAppointments();
      });
      actions.append(cancel);
    }
    card.append(actions);
    return card;
  });
  appointmentList.replaceChildren(...cards);
}

/* ---------- doctor: availability management ------------------------------ */
function initSlotManager() {
  const form = document.getElementById("slotForm");
  const statusLine = document.getElementById("slotFormStatus");

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const startLocal = document.getElementById("slotStart").value;
    const endLocal = document.getElementById("slotEnd").value;
    if (!startLocal || !endLocal) return;

    // datetime-local is interpreted in the browser's timezone; send UTC ISO.
    const payload = {
      start_time: new Date(startLocal).toISOString(),
      end_time: new Date(endLocal).toISOString(),
    };
    const { ok, data } = await api("/api/slots", { method: "POST", body: payload });
    statusLine.textContent = ok
      ? "Slot added."
      : data.error || "Could not add slot.";
    if (ok) {
      form.reset();
      await loadMySlots();
    }
  });

  loadMySlots();
}

async function loadMySlots() {
  const box = document.getElementById("mySlots");
  const { ok, data } = await api(`/api/doctors/${me.id}/slots`);
  if (!ok) {
    box.replaceChildren(emptyState("Could not load your slots.", { compact: true }));
    return;
  }
  if (!data.slots.length) {
    box.replaceChildren(emptyState("No open slots yet — add one above.", { compact: true }));
    return;
  }
  const chips = data.slots.map((s) => {
    const chip = el("span", "slot-chip");
    chip.append(el("span", null, formatSlot(s)));
    const del = el("button", "slot-chip-x", "×");
    del.type = "button";
    del.title = "Remove slot";
    del.addEventListener("click", async () => {
      const res = await api(`/api/slots/${s.id}`, { method: "DELETE" });
      if (!res.ok) window.alert(res.data.error || "Could not remove slot.");
      await loadMySlots();
    });
    chip.append(del);
    return chip;
  });
  box.replaceChildren(...chips);
}

init();
