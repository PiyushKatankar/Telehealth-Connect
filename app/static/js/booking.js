/* Booking page: doctor picker, live slot grid (Socket.IO), transactional booking. */
"use strict";

const socket = io();
let selectedDoctor = null; // user id of the doctor
let selectedSlot = null; // slot object currently selected
const openSlots = new Map(); // slot id -> slot object (open slots of selected doctor)

const doctorList = document.getElementById("doctorList");
const slotArea = document.getElementById("slotArea");
const bookBtn = document.getElementById("bookBtn");
const statusBox = document.getElementById("bookingStatus");
const resultBox = document.getElementById("bookingResult");
const loginNotice = document.getElementById("loginNotice");

/* ---------- live availability ------------------------------------------ */
socket.on("slot_update", (slot) => {
  if (slot.doctor_id !== selectedDoctor) return;
  if (slot.status === "open") openSlots.set(slot.id, slot);
  else openSlots.delete(slot.id);
  if (selectedSlot && selectedSlot.id === slot.id && slot.status !== "open") {
    selectedSlot = null; // someone else took it while we were choosing
  }
  renderSlots();
  setStatus("Availability just changed — slot list refreshed live.");
});

/* ---------- doctors ------------------------------------------------------ */
async function loadDoctors() {
  const { ok, data } = await api("/api/doctors");
  if (!ok) {
    doctorList.replaceChildren(el("p", "muted", "Could not load doctors."));
    return;
  }
  if (!data.doctors.length) {
    doctorList.replaceChildren(el("p", "muted", "No doctors available yet."));
    return;
  }
  const cards = data.doctors.map((d) => {
    const card = el("button", "doctor-item");
    card.type = "button";
    card.append(avatarFor(d.full_name, "avatar-sm"));
    const info = el("div", "d-info");
    info.append(el("div", "d-name", d.full_name), el("div", "d-spec", d.specialty));
    card.append(info);
    card.append(el("span", "d-count", `${d.open_slots} open`));
    card.addEventListener("click", () => selectDoctor(d.id, card));
    return card;
  });
  doctorList.replaceChildren(...cards);
}

async function selectDoctor(doctorId, cardEl) {
  selectedDoctor = doctorId;
  selectedSlot = null;
  resultBox.hidden = true;
  loginNotice.hidden = true;
  document.querySelectorAll(".doctor-item").forEach((n) => n.classList.remove("selected"));
  cardEl.classList.add("selected");
  socket.emit("subscribe_doctor", { doctor_id: doctorId });
  await loadSlots();
}

/* ---------- slots -------------------------------------------------------- */
async function loadSlots() {
  slotArea.replaceChildren(el("p", "muted", "Loading availability…"));
  const { ok, data } = await api(`/api/doctors/${selectedDoctor}/slots`);
  openSlots.clear();
  if (!ok) {
    slotArea.replaceChildren(el("p", "muted", "Could not load slots."));
    return;
  }
  data.slots.forEach((s) => openSlots.set(s.id, s));
  renderSlots();
}

function renderSlots() {
  if (!selectedDoctor) {
    slotArea.replaceChildren(emptyState("Select a doctor to see their availability.", { compact: true }));
    return;
  }
  if (!openSlots.size) {
    slotArea.replaceChildren(emptyState("No open slots for this doctor right now.", { compact: true }));
    bookBtn.disabled = true;
    return;
  }

  // Group slots by calendar day (viewer's local timezone).
  const byDay = new Map();
  openSlots.forEach((s) => {
    const key = new Date(s.start_time).toDateString();
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(s);
  });

  const frag = document.createDocumentFragment();
  byDay.forEach((slots, dayKey) => {
    const section = el("div", "slot-day");
    section.append(el("h3", "slot-day-title", dayKey));
    const grid = el("div", "slot-grid");
    slots
      .sort((a, b) => a.start_time.localeCompare(b.start_time))
      .forEach((s) => {
        const btn = el("button", "slot-btn", fmtTime(new Date(s.start_time)));
        btn.type = "button";
        if (selectedSlot && selectedSlot.id === s.id) btn.classList.add("selected");
        btn.addEventListener("click", () => {
          selectedSlot = s;
          document.querySelectorAll(".slot-btn").forEach((n) => n.classList.remove("selected"));
          btn.classList.add("selected");
          bookBtn.disabled = false;
        });
        grid.append(btn);
      });
    section.append(grid);
    frag.append(section);
  });
  slotArea.replaceChildren(frag);
  bookBtn.disabled = !selectedSlot;
}

/* ---------- booking ------------------------------------------------------ */
bookBtn.addEventListener("click", async () => {
  if (!selectedSlot) return;
  bookBtn.disabled = true;
  setStatus("Booking…");
  resultBox.hidden = true;
  loginNotice.hidden = true;

  const { ok, status, data } = await api("/api/appointments", {
    method: "POST",
    body: {
      slot_id: selectedSlot.id,
      symptoms: document.getElementById("symptoms").value,
    },
  });

  if (ok) {
    const a = data.appointment;
    document.getElementById("bookingResultText").textContent =
      `Your appointment with ${doctorLabel(a.doctor.full_name)} is confirmed for ${formatSlot(a.slot)}.`;
    document.getElementById("chatLink").href = `/chat/${a.id}`;
    resultBox.hidden = false;
    openSlots.delete(selectedSlot.id);
    selectedSlot = null;
    renderSlots();
    setStatus("");
    return;
  }

  bookBtn.disabled = false;
  if (status === 401) {
    loginNotice.hidden = false;
    setStatus("");
  } else {
    // 409: the slot was taken microseconds ago by someone else.
    setStatus(data.error || "Booking failed.");
    await loadSlots(); // refresh from the server
  }
});

function setStatus(text) {
  statusBox.textContent = text;
}

loadDoctors();
