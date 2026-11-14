/* Login form -> POST /api/auth/login -> redirect. */
"use strict";

document.getElementById("loginForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const errorBox = document.getElementById("loginError");
  clearError(errorBox);

  const { ok, data } = await api("/api/auth/login", {
    method: "POST",
    body: {
      email: document.getElementById("email").value,
      password: document.getElementById("password").value,
    },
  });

  if (!ok) {
    showError(errorBox, data.error || "Login failed.");
    return;
  }
  const next = new URLSearchParams(window.location.search).get("next");
  window.location.href = next && next.startsWith("/") ? next : "/dashboard";
});
