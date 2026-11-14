/* Register form -> POST /api/auth/register -> auto-login -> dashboard. */
"use strict";

const form = document.getElementById("registerForm");
const doctorFields = document.getElementById("doctorFields");
const errorBox = document.getElementById("registerError");
const specialtyInput = document.getElementById("specialty");

/* Show/hide the clinical fields based on the selected role. */
function syncDoctorFields() {
  const checked = form.querySelector('input[name="role"]:checked');
  doctorFields.hidden = !checked || checked.value !== "doctor";
}

form.addEventListener("change", (ev) => {
  if (ev.target.name === "role") syncDoctorFields();
});

/* Browsers restore previously-checked radios on back/forward navigation
   WITHOUT firing a change event — sync once on load so a restored
   "Doctor" role always shows the specialty fields. */
syncDoctorFields();

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
    payload.specialty = specialtyInput.value;
    payload.bio = document.getElementById("bio").value;
    if (!payload.specialty.trim()) {
      doctorFields.hidden = false; // never leave a required field invisible
      specialtyInput.focus();
      showError(errorBox, "Specialty is required for doctor accounts — e.g. Cardiology, Pediatrics.");
      return;
    }
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
