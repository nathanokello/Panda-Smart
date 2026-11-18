/*
  Shared page shell and helpers: sign-in check, role-based menu, formatting.
  Pages call PandaUI.init({ roles: [...], active: "lots" }) and get the user back.
*/
(function () {
  const ROLE_LABELS = {
    farmer: "Farmer",
    agent: "Storage agent",
    coop_admin: "Cooperative admin",
    admin: "Administrator"
  };
  const STAFF = ["agent", "coop_admin", "admin"];

  // Only pages that exist and work are listed. Nothing here is a placeholder.
  const NAV = [
    { key: "home", href: "index.html", icon: "⌂", label: "Dashboard", roles: ["farmer", ...STAFF] },
    { key: "farm", href: "farm.html", icon: "♧", label: "My farm", roles: ["farmer"] },
    { key: "geoagri", href: "geoagri.html", icon: "⌖", label: "GEOAGRI INTELLIGENCE", roles: ["farmer", ...STAFF] },
    { key: "seasons", href: "seasons.html", icon: "◷", label: "Seasons & soil", roles: ["farmer"] },
    { key: "farmers", href: "farmers.html", icon: "♟", label: "Farmers", roles: STAFF },
    { key: "lots", href: "lots.html", icon: "▣", label: "Hifadhi Mavuno", roles: ["farmer", ...STAFF] },
    { key: "marketplace", href: "marketplace.html", icon: "🛒", label: "Marketplace", roles: ["farmer", ...STAFF] },
    { key: "advice", href: "advice.html", icon: "❧", label: "Planting", roles: ["farmer", ...STAFF] },
    { key: "wards", href: "wards.html", icon: "▥", label: "Ward dashboard", roles: ["coop_admin", "admin"] },
    { key: "users", href: "users.html", icon: "⚙", label: "Users", roles: ["coop_admin", "admin"] },
    { key: "privacy", href: "privacy.html", icon: "⬡", label: "Privacy", roles: ["farmer", ...STAFF] }
  ];

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));

  function num(value, digits = 2) {
    if (value === null || value === undefined || value === "") return "—";
    const n = Number(value);
    if (!Number.isFinite(n)) return esc(value);
    return n.toLocaleString("en-KE", { maximumFractionDigits: digits });
  }
  function date(value) {
    if (!value) return "—";
    const d = new Date(value.length === 10 ? value + "T00:00:00" : value);
    return Number.isNaN(d.getTime()) ? esc(value)
      : d.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
  }
  function dateTime(value) {
    if (!value) return "—";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? esc(value)
      : d.toLocaleString("en-KE", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  const param = (name) => new URLSearchParams(location.search).get(name);
  const label = (code) => String(code || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

  let cropCache = null;
  async function crops() {
    if (!cropCache) cropCache = await PandaAPI.crops();
    return cropCache;
  }
  // "Maize · Mahindi": both languages, from the backend's crop list.
  function cropName(code) {
    const crop = (cropCache || []).find((c) => c.code === code);
    return crop ? `${esc(crop.name_en)} <span class="muted">· ${esc(crop.name_sw)}</span>` : esc(label(code));
  }

  function badge(text, tone) {
    return `<span class="badge badge-${tone}">${esc(text)}</span>`;
  }
  function lotStatusBadge(status) {
    const tones = { stored: "green", sold: "blue", disputed: "red", closed: "grey" };
    return badge(label(status), tones[status] || "grey");
  }
  // Architecture 7.4: Awaiting farmer / Verified / Disputed, from the event history.
  function verifyState(events) {
    const last = [...(events || [])].reverse().find((e) => e.type === "VERIFIED" || e.type === "DISPUTED");
    if (!last) return { key: "awaiting", html: badge("Awaiting farmer", "amber") };
    return last.type === "VERIFIED"
      ? { key: "verified", html: badge("Verified by farmer", "green") }
      : { key: "disputed", html: badge("Disputed by farmer", "red") };
  }

  function message(el, text, tone = "error") {
    if (!el) return;
    el.textContent = text || "";
    el.className = `form-message ${text ? "msg-" + tone : ""}`;
  }
  // Disable a button while a request runs, so a slow network can't double-submit.
  async function busy(button, task) {
    const original = button ? button.innerHTML : "";
    if (button) { button.disabled = true; button.innerHTML = "Please wait…"; }
    try { return await task(); } finally {
      if (button) { button.disabled = false; button.innerHTML = original; }
    }
  }
  function options(list, valueFn, textFn, placeholder) {
    return (placeholder ? `<option value="">${esc(placeholder)}</option>` : "") +
      list.map((item) => `<option value="${esc(valueFn(item))}">${esc(textFn(item))}</option>`).join("");
  }
  const wardText = (w) => w ? `${w.name}, ${w.county}` : "—";

  function buildShell(user, active) {
    const sidebar = document.getElementById("sidebar");
    if (sidebar) {
      const links = NAV.filter((item) => item.roles.includes(user.role)).map((item) =>
        `<a class="nav-link ${item.key === active ? "active" : ""}" href="${item.href}">` +
        `<span class="nav-icon">${item.icon}</span>${esc(item.label)}</a>`).join("");
      sidebar.innerHTML = `
        <a class="brand" href="index.html" aria-label="Panda Smart home">
          <img src="assets/panda-smart-logo.jpg" alt="Panda Smart logo"></a>
        <nav class="side-nav" aria-label="Main navigation">${links}</nav>
        <div class="sidebar-bottom">
          <button class="nav-link logout-button" id="logoutButton" type="button">
            <span class="nav-icon">⇥</span>Sign out</button>
        </div>`;
      document.getElementById("logoutButton").addEventListener("click", async () => {
        await PandaAPI.logout();
        location.href = "login.html";
      });
    }
    const menu = document.getElementById("menuButton");
    if (menu && sidebar) menu.addEventListener("click", () => sidebar.classList.toggle("sidebar-open"));
    const name = user.name || user.phone || "User";
    const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    set("userName", name);
    set("userRole", ROLE_LABELS[user.role] || user.role);
    set("userAvatar", name.charAt(0).toUpperCase());
  }

  // Sign-in check for every app page. Returns the current user or stops the page.
  async function init({ roles, active } = {}) {
    if (!PandaAPI.getToken()) {
      location.href = "login.html";
      return new Promise(() => {}); // page stops here
    }
    let user;
    try {
      user = await PandaAPI.me();
      PandaAPI.saveSession(PandaAPI.getToken(), user);
    } catch (error) {
      if (error.status === 401) return new Promise(() => {}); // api.js redirects
      const cached = PandaAPI.cachedUser();
      if (!cached) { location.href = "login.html"; return new Promise(() => {}); }
      user = cached;
      showBanner(`Could not reach the server: ${error.message}`);
    }
    buildShell(user, active);
    if (roles && !roles.includes(user.role)) {
      const content = document.querySelector(".dashboard-content");
      if (content) content.innerHTML = `<section class="panel"><h2>Not available for your account</h2>
        <p>This page is for ${roles.map((r) => ROLE_LABELS[r]).join(", ")} accounts.</p>
        <a class="button button-primary" href="index.html">Back to dashboard</a></section>`;
      return new Promise(() => {});
    }
    await crops().catch(() => { cropCache = []; });
    return user;
  }

  function showBanner(text) {
    const content = document.querySelector(".dashboard-content");
    if (!content) return;
    const div = document.createElement("p");
    div.className = "notice notice-error";
    div.textContent = text;
    content.prepend(div);
  }

  window.PandaUI = {
    ROLE_LABELS, STAFF, esc, num, date, dateTime, param, label, crops, cropName,
    badge, lotStatusBadge, verifyState, message, busy, options, wardText, init, showBanner,
    isStaff: (user) => STAFF.includes(user.role)
  };
})();
