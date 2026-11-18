/*
  users.html: staff accounts. Administrators manage all staff; cooperative
  admins manage storage agents in their own cooperative. The backend enforces
  the same rules (core/services.py MANAGEABLE_ROLES); this page only mirrors them.
*/
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, dateTime, ROLE_LABELS } = PandaUI;
  const me = await PandaUI.init({ roles: ["coop_admin", "admin"], active: "users" });
  const isAdmin = me.role === "admin";
  const creatable = isAdmin ? ["agent", "coop_admin", "admin"] : ["agent"];
  const rows = document.getElementById("userRows");
  const showInactive = document.getElementById("showInactive");
  const roleSel = document.getElementById("uRole");
  const tenantSel = document.getElementById("uTenant");
  const tenantWrap = document.getElementById("uTenantWrap");
  let users = [];
  let tenants = [];

  document.getElementById("scopeNote").textContent = isAdmin
    ? "You can manage every staff account."
    : "You can add and manage storage agents in your cooperative.";
  roleSel.innerHTML = PandaUI.options(creatable.map((r) => ({ r })), (o) => o.r, (o) => ROLE_LABELS[o.r]);

  try { tenants = await PandaAPI.tenants(); } catch (error) { PandaUI.showBanner(error.message); }
  tenantSel.innerHTML = PandaUI.options(tenants, (t) => t.id, (t) => `${t.name} (${PandaUI.label(t.type)})`, "Select cooperative");
  if (!isAdmin) {
    tenantWrap.hidden = true; // coop admins always add to their own cooperative
  }
  const syncTenant = () => {
    const needsTenant = roleSel.value !== "admin";
    tenantWrap.hidden = !isAdmin || !needsTenant;
    tenantSel.required = isAdmin && needsTenant;
  };
  roleSel.addEventListener("change", syncTenant);
  syncTenant();

  function statusBadge(u) {
    return u.is_active ? PandaUI.badge("Active", "green") : PandaUI.badge("Deactivated", "grey");
  }
  function render() {
    const list = users.filter((u) => showInactive.checked || u.is_active);
    rows.innerHTML = list.length ? list.map((u) => `
      <tr class="${u.can_manage ? "clickable" : ""}" data-id="${esc(u.id)}">
        <td>${u.can_manage ? `<a href="#" data-edit="${esc(u.id)}">${esc(u.name)}</a>` : esc(u.name)}${u.id === me.id ? ' <span class="muted small">(you)</span>' : ""}</td>
        <td>${esc(u.phone)}</td><td>${esc(ROLE_LABELS[u.role] || u.role)}</td>
        <td>${esc(u.tenant_name || "—")}</td><td>${u.last_login ? dateTime(u.last_login) : "Never"}</td>
        <td>${statusBadge(u)}</td></tr>`).join("")
      : `<tr><td colspan="6" class="empty-row">No accounts to show.</td></tr>`;
  }
  async function load() {
    try { users = await PandaAPI.users(); render(); }
    catch (error) { rows.innerHTML = `<tr><td colspan="6" class="empty-row">${esc(error.message)}</td></tr>`; }
  }
  showInactive.addEventListener("change", render);

  // ---- Create ----
  const form = document.getElementById("userForm");
  const message = document.getElementById("userMessage");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    PandaUI.message(message, "");
    const payload = {
      name: document.getElementById("uName").value.trim(),
      phone: document.getElementById("uPhone").value.trim(),
      role: roleSel.value,
      password: document.getElementById("uPassword").value
    };
    if (isAdmin && roleSel.value !== "admin") payload.tenant_id = tenantSel.value;
    try {
      const user = await PandaUI.busy(form.querySelector("button"), () => PandaAPI.createUser(payload));
      PandaUI.message(message, `${user.name} can now sign in with ${user.phone}.`, "success");
      form.reset();
      syncTenant();
      await load();
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  });

  // ---- Edit (only accounts the backend says you can manage) ----
  const panel = document.getElementById("editPanel");
  function openEditor(user) {
    panel.hidden = false;
    panel.innerHTML = `
      <h2>${esc(user.name)}</h2>
      <p class="muted small">${esc(user.phone)} · ${esc(ROLE_LABELS[user.role])} · ${statusBadge(user)}</p>
      <form id="editForm" class="form-grid">
        <div class="field full"><label for="eName">Name</label><input id="eName" value="${esc(user.name)}" maxlength="150"></div>
        ${isAdmin ? `<div class="field"><label for="eRole">Role</label><select id="eRole">
            ${creatable.map((r) => `<option value="${r}" ${r === user.role ? "selected" : ""}>${esc(ROLE_LABELS[r])}</option>`).join("")}</select></div>
          <div class="field"><label for="eTenant">Cooperative</label><select id="eTenant"><option value="">None (administrators only)</option>
            ${tenants.map((t) => `<option value="${esc(t.id)}" ${t.id === user.tenant_id ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</select></div>` : ""}
        <div class="field full"><label for="ePassword">New temporary password</label><input id="ePassword" type="password" minlength="8" autocomplete="new-password" placeholder="Leave blank to keep the current one"></div>
        <div class="full"><p class="form-message" id="editMessage" role="alert"></p>
          <div class="form-actions" style="margin-top:0">
            <button class="button button-primary" type="submit">Save changes</button>
            <button class="button ${user.is_active ? "button-danger" : "button-outline"}" style="margin:0" type="button" id="toggleActive">
              ${user.is_active ? "Deactivate" : "Reactivate"}</button>
          </div>
          <p class="hint muted small">Saving a new role, cooperative or password, or deactivating, signs this person out everywhere.</p></div>
      </form>`;
    const editMessage = document.getElementById("editMessage");
    const save = async (payload, button, done) => {
      PandaUI.message(editMessage, "");
      try {
        const updated = await PandaUI.busy(button, () => PandaAPI.updateUser(user.id, payload));
        await load();
        openEditor(updated);
        PandaUI.message(document.getElementById("editMessage"), done, "success");
      } catch (error) {
        PandaUI.message(editMessage, error.message);
      }
    };
    document.getElementById("editForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const payload = { name: document.getElementById("eName").value.trim() };
      if (isAdmin) {
        payload.role = document.getElementById("eRole").value;
        payload.tenant_id = document.getElementById("eTenant").value || null;
      }
      const pw = document.getElementById("ePassword").value;
      if (pw) payload.password = pw;
      save(payload, event.submitter, "Saved.");
    });
    document.getElementById("toggleActive").addEventListener("click", (event) => {
      if (user.is_active && !confirmDeactivate(user)) return;
      save({ is_active: !user.is_active }, event.currentTarget, user.is_active ? "Account deactivated." : "Account reactivated.");
    });
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  // A two-step check inside the page instead of a browser pop-up.
  let pendingDeactivate = null;
  function confirmDeactivate(user) {
    if (pendingDeactivate === user.id) { pendingDeactivate = null; return true; }
    pendingDeactivate = user.id;
    PandaUI.message(document.getElementById("editMessage"),
      `Click "Deactivate" again to confirm. ${user.name} will be signed out and unable to sign in.`, "info");
    return false;
  }
  rows.addEventListener("click", (event) => {
    const link = event.target.closest("[data-edit]");
    const row = event.target.closest("tr[data-id]");
    const id = link ? link.dataset.edit : row && row.classList.contains("clickable") ? row.dataset.id : null;
    if (!id) return;
    event.preventDefault();
    const user = users.find((u) => u.id === id);
    if (user) { pendingDeactivate = null; openEditor(user); }
  });

  await load();
});
