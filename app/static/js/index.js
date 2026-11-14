/* Landing page: render the public doctor directory. */
"use strict";

(async function initDoctors() {
  const list = document.getElementById("doctorList");
  const { ok, data } = await api("/api/doctors");
  if (!ok) {
    list.replaceChildren(emptyState("Could not load doctors.", { icon: "users" }));
    return;
  }
  if (!data.doctors.length) {
    list.replaceChildren(
      emptyState("No doctors have signed up yet. Register as a doctor to add availability.", { icon: "users" }),
    );
    return;
  }

  const cards = data.doctors.map((d) => {
    const card = el("article", "card doctor-card");

    const head = el("div", "doctor-card-head");
    head.append(avatarFor(d.full_name));
    const info = el("div", "d-info");
    info.append(el("h3", null, d.full_name), el("span", "d-spec", d.specialty));
    head.append(info);

    card.append(head, el("p", "d-bio", d.bio || "No bio yet."));

    const meta = el("div", "doctor-card-meta");
    meta.append(el("span", "badge badge-open", `${d.open_slots} open slot${d.open_slots === 1 ? "" : "s"}`));
    const book = el("a", "btn btn-primary btn-sm", "Book");
    book.href = "/booking";
    meta.append(book);
    card.append(meta);
    return card;
  });
  list.replaceChildren(...cards);
})();
