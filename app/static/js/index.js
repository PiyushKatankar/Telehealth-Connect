/* Landing page: render the public doctor directory. */
"use strict";

(async function initDoctors() {
  const list = document.getElementById("doctorList");
  const { ok, data } = await api("/api/doctors");
  if (!ok) {
    list.replaceChildren(el("p", "muted", "Could not load doctors."));
    return;
  }
  if (!data.doctors.length) {
    list.replaceChildren(el("p", "muted", "No doctors have signed up yet. Register as a doctor to add availability."));
    return;
  }

  const cards = data.doctors.map((d) => {
    const card = el("article", "card doctor-card");
    const head = el("div", "doctor-card-head");
    head.append(el("h3", null, d.full_name), el("span", "badge badge-specialty", d.specialty));
    card.append(head, el("p", "muted", d.bio || "No bio yet."));
    const meta = el("p", "doctor-card-meta");
    meta.append(el("span", "badge badge-open", `${d.open_slots} open slot${d.open_slots === 1 ? "" : "s"}`));
    const book = el("a", "btn btn-primary btn-sm", "Book");
    book.href = "/booking";
    meta.append(book);
    card.append(meta);
    return card;
  });
  list.replaceChildren(...cards);
})();
