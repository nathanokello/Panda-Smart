/*
  farm.html: a farmer's own record and plots, or (for staff) any farmer in
  their cooperative via farm.html?farmer=<id>, including that farmer's lots.
*/
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, date, wardText } = PandaUI;
  const user = await PandaUI.init({ active: PandaUI.param("farmer") ? "farmers" : "farm" });
  const staff = PandaUI.isStaff(user);
  const farmerId = staff ? PandaUI.param("farmer") : user.farmer_id;
  const profile = document.getElementById("profilePanel");
  const plotRows = document.getElementById("plotRows");

  if (!farmerId) {
    profile.innerHTML = staff
      ? `<h2>No farmer selected</h2><p><a href="farmers.html">Choose a farmer from the list</a>.</p>`
      : `<h2>No farmer record</h2><p class="muted">Your login is not linked to a farmer record. Ask your storage agent or cooperative to link it.</p>`;
    plotRows.innerHTML = `<tr><td colspan="3" class="empty-row">—</td></tr>`;
    document.getElementById("plotForm").querySelector("button").disabled = true;
    return;
  }

  let wards = [];
  async function load() {
    try {
      const [farmer, plots] = await Promise.all([PandaAPI.farmer(farmerId), PandaAPI.plots(farmerId)]);
      document.getElementById("pageTitle").textContent = staff ? farmer.name : "My farm";
      profile.innerHTML = `
        <h2>${esc(farmer.name)}</h2>
        <dl class="kv">
          <dt>Phone</dt><dd>${esc(farmer.phone)}</dd>
          <dt>Ward</dt><dd>${esc(wardText(farmer.ward))}</dd>
          <dt>Consent</dt><dd>${farmer.consent_given ? "Given " + date(farmer.consent_at) : "Not given"}</dd>
          <dt>Registered</dt><dd>${date(farmer.created_at)}</dd>
        </dl>
        <div class="form-actions">
          <a class="button button-outline button-small" style="margin:0" href="seasons.html${staff ? "?farmer=" + encodeURIComponent(farmer.id) : ""}">Seasons &amp; soil</a>
          ${staff ? `<a class="button button-primary button-small" href="lots.html?farmer=${encodeURIComponent(farmer.id)}">Register a lot for this farmer</a>` : ""}
        </div>`;
      const pw = document.getElementById("pWard");
      if (!pw.value && farmer.ward) pw.value = farmer.ward.id;
      plotRows.innerHTML = plots.length ? plots.map((p) => {
        const ward = wards.find((w) => w.id === p.ward_id);
        return `<tr><td>${esc(wardText(ward))}</td><td>${num(p.acres)}</td><td>${date(p.created_at)}</td></tr>`;
      }).join("") : `<tr><td colspan="3" class="empty-row">No plots yet. Add one with the form.</td></tr>`;
    } catch (error) {
      profile.innerHTML = `<h2>Could not load the farmer</h2><p class="muted">${esc(error.message)}</p>`;
    }
  }

  async function loadLots() {
    const panel = document.getElementById("lotsPanel");
    panel.hidden = false;
    const body = document.getElementById("farmerLotRows");
    try {
      const lots = await PandaAPI.lots({ farmer: farmerId });
      body.innerHTML = lots.length ? lots.map((lot) => `
        <tr class="clickable" onclick="location.href='lot.html?id=${encodeURIComponent(lot.id)}'">
          <td><a href="lot.html?id=${encodeURIComponent(lot.id)}">${PandaUI.cropName(lot.crop)}</a></td>
          <td>${num(lot.initial_weight_kg)} kg</td><td>${num(lot.summary.latest_weight_kg)} kg</td>
          <td>${num(lot.summary.loss_pct)}%</td><td>${PandaUI.lotStatusBadge(lot.status)}</td></tr>`).join("")
        : `<tr><td colspan="5" class="empty-row">No lots for this farmer.</td></tr>`;
    } catch (error) {
      body.innerHTML = `<tr><td colspan="5" class="empty-row">${esc(error.message)}</td></tr>`;
    }
  }

  try {
    wards = await PandaAPI.wards();
    document.getElementById("pWard").innerHTML = PandaUI.options(wards, (w) => w.id, wardText, "Select ward");
  } catch (error) {
    PandaUI.showBanner(error.message);
  }
  await load();
  if (staff) loadLots();

  const form = document.getElementById("plotForm");
  const message = document.getElementById("plotMessage");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    PandaUI.message(message, "");
    try {
      await PandaUI.busy(form.querySelector("button"), () => PandaAPI.createPlot(farmerId, {
        ward: document.getElementById("pWard").value,
        acres: document.getElementById("pAcres").value
      }));
      PandaUI.message(message, "Plot added.", "success");
      document.getElementById("pAcres").value = "";
      await load();
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  });
});
