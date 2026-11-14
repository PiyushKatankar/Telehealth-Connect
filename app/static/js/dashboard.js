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
    me.role === "doctor" ? `Dr. ${me.full_name}` : `Welcome, ${me.full_name}`;

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
      el("p", "muted", "No appointments yet. Use “Book a new appointment” to get started."),
    );
    return;
  }

  const cards = data.appointments.map((a) => {
    const card = el("article", "card appointment-card");
    const head = el("div", "appointment-head");
    head.append(
      el("strong", null, me.role === "doctor" ? `Patient: ${a.patient.full_name}` : `Dr. ${a.doctor.full_name}`),
      el("span", `badge badge-${a.status}`, a.status),
    );
    card.append(head, el("p", null, a.slot ? formatSlot(a.slot) : "—"));
    if (a.symptoms) card.append(el("p", "muted", `Symptoms: ${a.symptoms}`));

    const actions = el("div", "appointment-actions");
    if (a.status === "scheduled") {
      const chat = el("a", "btn btn-primary btn-sm", "Chat");
      chat.href = `/chat/${a.id}`;
      actions.append(chat);

      const cancel = el("button", "btn btn-ghost btn-sm", "Cancel");
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
    box.replaceChildren(el("p", "muted", "Could not load your slots."));
    return;
  }
  if (!data.slots.length) {
    box.replaceChildren(el("p", "muted", "No open slots yet — add one above."));
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
