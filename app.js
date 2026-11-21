// Renders the store's apps from data/apps.json (refreshed by scripts/update-store).
(async () => {
  const el = document.getElementById("store-list");
  try {
    const res = await fetch("data/apps.json");
    if (!res.ok) throw new Error(res.status);
    const { apps } = await res.json();
    el.replaceChildren(...apps.map(card));
  } catch (e) {
    el.textContent = "The app list could not be loaded. Open Settings → Software on Dazzle to browse it.";
  }

  function card(a) {
    const c = document.createElement("article");
    c.className = "card app";
    c.id = "app-" + a.name;
    const shot = a.screenshot
      ? `<div class="shot"><img src="${esc(a.screenshot)}" alt="Screenshot of ${esc(a.title)}" loading="lazy"></div>`
      : "";
    const icon = a.icon ? `<img src="${esc(a.icon)}" alt="" width="44" height="44">` : "";
    c.innerHTML = `${shot}<div class="body"><div class="head">${icon}<div><h3>${esc(a.title)}</h3><small>${esc(a.description)}</small></div></div><p>${esc(a.about)}</p></div>`;
    return c;
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  }
})();
