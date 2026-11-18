/* lots.html: list grain lots (staff) and register a new lot (agents, admins). */
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, date } = PandaUI;
  const user = await PandaUI.init({ roles: ["farmer", ...PandaUI.STAFF], active: "lots" });
  const canWrite = user.role === "agent" || user.role === "admin";
  const rows = document.getElementById("lotRows");
  const statusFilter = document.getElementById("statusFilter");
  const cropFilter = document.getElementById("cropFilter");
  let farmersById = {};

  const crops = await PandaUI.crops();
  cropFilter.innerHTML += PandaUI.options(crops, (c) => c.code, (c) => `${c.name_en} · ${c.name_sw}`);

  async function load() {
    rows.innerHTML = `<tr><td colspan="7" class="empty-row">Loading…</td></tr>`;
    try {
      const lots = await PandaAPI.lots({
        status: statusFilter.value, crop: cropFilter.value, farmer: PandaUI.param("farmer")
      });
      rows.innerHTML = lots.length ? lots.map((lot) => {
        const farmer = farmersById[lot.farmer_id];
        const farmerName = user.role === "farmer" ? user.name : (farmer ? farmer.name : "—");
        const href = `lot.html?id=${encodeURIComponent(lot.id)}`;
        return `<tr class="clickable" data-href="${href}">
          <td><a href="${href}">${date(lot.registered_at)}</a></td>
          <td>${esc(farmerName)}</td>
          <td>${PandaUI.cropName(lot.crop)}</td>
          <td>${num(lot.initial_weight_kg)} kg</td>
          <td>${num(lot.summary.latest_weight_kg)} kg</td>
          <td>${num(lot.summary.loss_kg)} kg <span class="muted">(${num(lot.summary.loss_pct)}%)</span></td>
          <td>${PandaUI.lotStatusBadge(lot.status)}</td></tr>`;
      }).join("") : `<tr><td colspan="7" class="empty-row">No lots match.</td></tr>`;
    } catch (error) {
      rows.innerHTML = `<tr><td colspan="7" class="empty-row">${esc(error.message)}</td></tr>`;
    }
  }
  rows.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-href]");
    if (row && event.target.tagName !== "A") location.href = row.dataset.href;
  });
  statusFilter.addEventListener("change", load);
  cropFilter.addEventListener("change", load);

  let farmers = [];
  if (PandaUI.isStaff(user)) {
    try {
      farmers = await PandaAPI.farmers();
      farmersById = Object.fromEntries(farmers.map((f) => [f.id, f]));
    } catch (error) {
      PandaUI.showBanner(`Farmers could not be loaded: ${error.message}`);
    }
  }
  await load();

  if (!canWrite) return; // coop admins can view but not register lots
  document.getElementById("lotFormPanel").hidden = false;
  const farmerSelect = document.getElementById("lFarmer");
  const consenting = farmers.filter((f) => f.consent_given);
  farmerSelect.innerHTML = consenting.length
    ? PandaUI.options(consenting, (f) => f.id, (f) => `${f.name} (${f.phone})`, "Select farmer")
    : `<option value="">No farmers yet</option>`;
  if (PandaUI.param("farmer")) farmerSelect.value = PandaUI.param("farmer");
  const storable = crops.filter((c) => c.storable);
  document.getElementById("lCrop").innerHTML =
    PandaUI.options(storable, (c) => c.code, (c) => `${c.name_en} · ${c.name_sw}`);
  if (storable.some((c) => c.code === "maize")) document.getElementById("lCrop").value = "maize";

  const form = document.getElementById("lotForm");
  const message = document.getElementById("lotMessage");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    PandaUI.message(message, "");
    const moisture = document.getElementById("lMoisture").value;
    try {
      const lot = await PandaUI.busy(form.querySelector("button"), () => PandaAPI.createLot({
        farmer_id: farmerSelect.value,
        crop: document.getElementById("lCrop").value,
        weight_kg: document.getElementById("lWeight").value,
        bag_count: Number(document.getElementById("lBags").value),
        storage_method: document.getElementById("lMethod").value,
        location_label: document.getElementById("lLocation").value.trim(),
        moisture_pct: moisture === "" ? null : moisture
      }));
      location.href = `lot.html?id=${encodeURIComponent(lot.id)}&new=1`;
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  });
});
