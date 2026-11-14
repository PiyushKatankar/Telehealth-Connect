/* Register form -> POST /api/auth/register -> auto-login -> dashboard. */
"use strict";

const form = document.getElementById("registerForm");
const doctorFields = document.getElementById("doctorFields");
const errorBox = document.getElementById("registerError");

/* Show/hide clinical fields based on the selected role. */
form.addEventListener("change", (ev) => {
  if (ev.target.name === "role") {
    doctorFields.hidden = ev.target.value !== "doctor";
  }
});

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  clearError(errorBox);

  const role = form.querySelector('input[name="role"]:checked').value;
  const payload = {
    role,
    full_name: document.getElementById("fullName").value,
    email: document.getElementById("email").value,
    password: document.getElementById("password").value,
  };
  if (role === "doctor") {
    payload.specialty = document.getElementById("specialty").value;
    payload.bio = document.getElementById("bio").value;
  }

  const reg = await api("/api/auth/register", { method: "POST", body: payload });
  if (!reg.ok) {
    showError(errorBox, reg.data.error || "Registration failed.");
    return;
  }

  // A fresh account has no session yet — log the user in right away.
  const login = await api("/api/auth/login", {
    method: "POST",
    body: { email: payload.email, password: payload.password },
  });
  if (!login.ok) {
    window.location.href = "/login";
    return;
  }
  window.location.href = "/dashboard";
});
