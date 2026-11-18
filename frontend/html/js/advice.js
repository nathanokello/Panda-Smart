/*
  advice.html: rule-based planting advice, planting windows (slots) and
  planting plans (intents). Farmers plan for themselves; staff pick a farmer.
*/
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, date, wardText } = PandaUI;
  const user = await PandaUI.init({ active: "advice" });
  const staff = PandaUI.isStaff(user);
  const season = window.PANDA_CONFIG.DEFAULT_SEASON;

  const [wards, crops] = await Promise.all([PandaAPI.wards().catch(() => []), PandaUI.crops()]);
  const cropText = (c) => `${c.name_en} · ${c.name_sw}`;
  const wardSel = document.getElementById("aWard");
  const cropSel = document.getElementById("aCrop");
  wardSel.innerHTML = PandaUI.options(wards, (w) => w.id, wardText, "Select ward");
  cropSel.innerHTML = PandaUI.options(crops, (c) => c.code, cropText);
  document.getElementById("iCrop").innerHTML = PandaUI.options(crops, (c) => c.code, cropText);

  let myFarmer = null;
  let farmers = [];
  if (!staff && user.farmer_id) {
    try { myFarmer = await PandaAPI.farmer(user.farmer_id); } catch { /* handled below */ }
  }
  if (myFarmer && myFarmer.ward) wardSel.value = myFarmer.ward.id;

  // ---- Advice and slots ----
  const adviceResult = document.getElementById("adviceResult");
  const slotResult = document.getElementById("slotResult");
  const adviceMessage = document.getElementById("adviceMessage");
  async function showAdvice() {
    PandaUI.message(adviceMessage, "");
    if (!wardSel.value) { PandaUI.message(adviceMessage, "Choose a ward."); return; }
    adviceResult.innerHTML = `<p class="muted">Loading…</p>`;
    try {
      const a = await PandaAPI.advice(wardSel.value, cropSel.value);
      const pct = Math.round(Number(a.confidence) * 100);
      const level = pct >= 75 ? ["Higher", "green"] : pct >= 55 ? ["Medium", "amber"] : ["Lower", "red"];
      adviceResult.innerHTML = `
        <div class="figure-row" style="margin-top:16px">
          <div class="figure"><strong>${date(a.recommended_window.start)} – ${date(a.recommended_window.end)}</strong><span>Suggested planting window</span></div>
          <div class="figure"><strong>${pct}%</strong><span>Confidence: ${PandaUI.badge(level[0], level[1])}</span></div>
        </div>
        <p>${esc(a.rationale)}</p>
        ${a.alternatives && a.alternatives.length ? `<p>Also worth considering: ${a.alternatives.map(PandaUI.cropName).join(", ")}</p>` : ""}
        <p class="muted small">Rule set ${esc(a.rule_set_version)}. Confidence is a score from the rules, not a measured probability.</p>`;
    } catch (error) {
      adviceResult.innerHTML = "";
      PandaUI.message(adviceMessage, error.message);
    }
    try {
      const slots = await PandaAPI.slots(wardSel.value, cropSel.value, season);
      slotResult.innerHTML = slots.length ? `<div class="table-wrap"><table class="data-table">
        <thead><tr><th>Window</th><th>Capacity</th><th>Planned</th><th>Still open</th></tr></thead><tbody>
        ${slots.map((s) => `<tr><td>${date(s.window_start)} – ${date(s.window_end)}</td><td>${num(s.capacity_acres)} ac</td>
          <td>${num(s.booked_acres)} ac</td><td>${s.remaining_acres > 0 ? num(s.remaining_acres) + " ac" : PandaUI.badge("Full", "red")}</td></tr>`).join("")}
        </tbody></table></div><p class="muted small">Season ${esc(season)}.</p>`
        : `<p class="muted">No planting windows set for this crop in this ward yet.</p>`;
    } catch (error) {
      slotResult.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
    }
  }
  document.getElementById("adviceForm").addEventListener("submit", (e) => { e.preventDefault(); showAdvice(); });
  if (wardSel.value) showAdvice();

  // ---- Planting plans ----
  const farmerSel = document.getElementById("iFarmer");
  const plotSel = document.getElementById("iPlot");
  async function loadPlots(farmerId) {
    plotSel.innerHTML = `<option value="">No specific plot</option>`;
    if (!farmerId) return;
    try {
      const plots = await PandaAPI.plots(farmerId);
      plotSel.innerHTML += PandaUI.options(plots, (p) => p.id, (p) => `${num(p.acres)} acres (added ${date(p.created_at)})`);
    } catch { /* plots are optional */ }
  }
  if (staff) {
    document.getElementById("iFarmerWrap").hidden = false;
    farmerSel.required = true;
    try { farmers = await PandaAPI.farmers(); } catch (error) { PandaUI.showBanner(error.message); }
    farmerSel.innerHTML = PandaUI.options(farmers.filter((f) => f.consent_given), (f) => f.id, (f) => `${f.name} (${f.phone})`, "Select farmer");
    farmerSel.addEventListener("change", () => loadPlots(farmerSel.value));
    document.getElementById("intentListTitle").textContent = "Planting plans in your cooperative";
  } else {
    document.getElementById("intentListTitle").textContent = "My planting plans";
    await loadPlots(user.farmer_id);
  }

  const intentRows = document.getElementById("intentRows");
  async function loadIntents() {
    try {
      const intents = await PandaAPI.intents();
      const byId = Object.fromEntries(farmers.map((f) => [f.id, f]));
      intentRows.innerHTML = intents.length ? intents.slice(0, 50).map((i) => `<tr>
        <td>${PandaUI.cropName(i.crop)}${staff && byId[i.farmer_id] ? `<br><span class="muted small">${esc(byId[i.farmer_id].name)}</span>` : ""}</td>
        <td>${num(i.acres)}</td>
        <td>${i.slot ? `${date(i.slot.window_start)} – ${date(i.slot.window_end)}` : "—"}</td>
        <td>${i.oversubscribed ? PandaUI.badge("Moved: above demand", "amber") : ""}</td></tr>`).join("")
        : `<tr><td colspan="4" class="empty-row">No planting plans yet.</td></tr>`;
    } catch (error) {
      intentRows.innerHTML = `<tr><td colspan="4" class="empty-row">${esc(error.message)}</td></tr>`;
    }
  }

  const form = document.getElementById("intentForm");
  const message = document.getElementById("intentMessage");
  const result = document.getElementById("intentResult");
  if (!staff && !user.farmer_id) {
    form.querySelector("button").disabled = true;
    PandaUI.message(message, "Your login is not linked to a farmer record, so you can't submit a plan yet.");
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    PandaUI.message(message, "");
    result.innerHTML = "";
    try {
      const intent = await PandaUI.busy(form.querySelector("button"), () => PandaAPI.createIntent({
        farmer_id: staff ? farmerSel.value : user.farmer_id,
        plot_id: plotSel.value || null,
        crop: document.getElementById("iCrop").value,
        acres: document.getElementById("iAcres").value,
        season
      }));
      result.innerHTML = `
        <div class="notice ${intent.oversubscribed ? "notice-warn" : ""}" style="margin-top:14px">
          ${intent.slot ? `Planting window: <strong>${date(intent.slot.window_start)} – ${date(intent.slot.window_end)}</strong>.` : "No planting window is set for this crop and ward yet."}
          ${intent.warning ? `<br>${esc(intent.warning)}` : ""}
          ${intent.alternatives && intent.alternatives.length ? `<br>Alternatives: ${intent.alternatives.map((a) => `${PandaUI.cropName(a.crop)} (${esc(a.reason)})`).join("; ")}` : ""}
        </div>`;
      document.getElementById("iAcres").value = "";
      await loadIntents();
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  });
  await loadIntents();
});
