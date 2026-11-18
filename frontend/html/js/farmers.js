/* farmers.html: list farmers in the agent's cooperative and register new ones. */
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, wardText } = PandaUI;
  await PandaUI.init({ roles: PandaUI.STAFF, active: "farmers" });
  const rows = document.getElementById("farmerRows");
  const search = document.getElementById("farmerSearch");
  let farmers = [];

  function render() {
    const q = search.value.trim().toLowerCase();
    const list = farmers.filter((f) => !q || f.name.toLowerCase().includes(q) || f.phone.includes(q));
    rows.innerHTML = list.length ? list.map((f) => `
      <tr class="clickable" data-id="${esc(f.id)}">
        <td><a href="farm.html?farmer=${encodeURIComponent(f.id)}">${esc(f.name)}</a></td>
        <td>${esc(f.phone)}</td>
        <td>${esc(wardText(f.ward))}</td>
        <td>${num((f.plots || []).length, 0)}</td>
        <td>${f.consent_given ? PandaUI.badge("Given", "green") : PandaUI.badge("Missing", "red")}</td>
      </tr>`).join("")
      : `<tr><td colspan="5" class="empty-row">${farmers.length ? "No farmer matches your search." : "No farmers registered yet."}</td></tr>`;
  }
  rows.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-id]");
    if (row && event.target.tagName !== "A") location.href = `farm.html?farmer=${encodeURIComponent(row.dataset.id)}`;
  });
  search.addEventListener("input", render);

  async function load() {
    try {
      farmers = await PandaAPI.farmers();
      render();
    } catch (error) {
      rows.innerHTML = `<tr><td colspan="5" class="empty-row">${esc(error.message)}</td></tr>`;
    }
  }

  const wardSelect = document.getElementById("fWard");
  PandaAPI.wards().then((wards) => {
    wardSelect.innerHTML = PandaUI.options(wards, (w) => w.id, wardText, "Select ward");
  }).catch((error) => { wardSelect.innerHTML = `<option value="">${esc(error.message)}</option>`; });

  const loginBox = document.getElementById("fLogin");
  const passwordWrap = document.getElementById("fPasswordWrap");
  loginBox.addEventListener("change", () => {
    passwordWrap.hidden = !loginBox.checked;
    document.getElementById("fPassword").required = loginBox.checked;
  });

  const form = document.getElementById("farmerForm");
  const message = document.getElementById("farmerMessage");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    PandaUI.message(message, "");
    const payload = {
      name: form.name.value.trim(),
      phone: form.phone.value.trim(),
      ward: wardSelect.value,
      consent_given: document.getElementById("fConsent").checked,
      create_login: loginBox.checked
    };
    if (loginBox.checked) payload.password = document.getElementById("fPassword").value;
    try {
      const farmer = await PandaUI.busy(form.querySelector("button[type=submit]"), () => PandaAPI.createFarmer(payload));
      PandaUI.message(message, `${farmer.name} registered (${farmer.phone}).`, "success");
      form.reset();
      passwordWrap.hidden = true;
      await load();
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  });

  await load();
});
