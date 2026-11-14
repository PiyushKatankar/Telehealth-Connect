/* Appointment chat: Socket.IO room + history replay. */
"use strict";

const socket = io();
const appointmentId = Number(document.body.dataset.appointmentId);
const messagesBox = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const noticeBox = document.getElementById("chatNotice");

let me = null;
const renderedMessageIds = new Set();

socket.on("connect", async () => {
  socket.emit("join_chat", { appointment_id: appointmentId });
  if (!me) {
    const { ok, data } = await api("/api/auth/me");
    if (ok) me = data.user;
  }
});

socket.on("chat_joined", ({ history }) => {
  history.forEach(appendMessage);
  scrollToEnd();
});

socket.on("chat_message", (msg) => appendMessage(msg));

socket.on("chat_error", ({ error }) => {
  noticeBox.textContent = error;
});

chatForm.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const body = chatInput.value.trim();
  if (!body) return;
  socket.emit("send_message", { appointment_id: appointmentId, body });
  chatInput.value = "";
});

function appendMessage(msg) {
  if (renderedMessageIds.has(msg.id)) return; // server also echoes to the sender
  renderedMessageIds.add(msg.id);

  const wrap = el(
    "div",
    `message ${msg.sender_id === (me && me.id) ? "message-own" : "message-other"}`,
  );
  const meta = el(
    "div",
    "message-meta",
    `${msg.sender_name || "User"} · ${new Date(msg.created_at).toLocaleString()}`,
  );
  const body = el("div", "message-body", msg.body);
  wrap.append(meta, body);
  messagesBox.append(wrap);
  scrollToEnd();
}

function scrollToEnd() {
  messagesBox.scrollTop = messagesBox.scrollHeight;
}
