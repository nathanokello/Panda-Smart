/*
  seasons.html: a farmer's past seasons and soil tests, and what worked before.
  Farmers see their own; staff open seasons.html?farmer=<id>.
*/
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, date } = PandaUI;
  const user = await PandaUI.init({ active: PandaUI.param("farmer") ? "farmers" : "seasons" });
  const staff = PandaUI.isStaff(user);
  const farmerId = staff ? PandaUI.param("farmer") : user.farmer_id;
  const learn = document.getElementById("learnPanel");
  if (!farmerId) {
    learn.innerHTML = staff
      ? `<h2>No farmer selected</h2><p><a href="farmers.html">Choose a farmer</a>, then open "Seasons &amp; soil".</p>`
      : `<h2>No farmer record</h2><p class="muted">Your login is not linked to a farmer record yet. Ask your storage agent or cooperative.</p>`;
    document.querySelectorAll("form button").forEach((b) => { b.disabled = true; });
    return;
  }

  // Season choices: this year and the four before, long and short rains.
  const year = new Date().getFullYear();
  const seasonOptions = [];
  for (let y = year; y >= year - 4; y -= 1) {
    seasonOptions.push(`${y}-short-rains`, `${y}-long-rains`);
  }
  const seasonText = (s) => {
    const [y, ...rest] = s.split("-");
    return `${rest.join(" ").replace(/^\w/, (c) => c.toUpperCase())} ${y}`;
  };
  document.getElementById("sSeason").innerHTML = PandaUI.options(seasonOptions.map((s) => ({ s })), (o) => o.s, (o) => seasonText(o.s));
  const crops = await PandaUI.crops();
  document.getElementById("sCrop").innerHTML = PandaUI.options(crops, (c) => c.code, (c) => `${c.name_en} · ${c.name_sw}`);
  if (crops.some((c) => c.code === "maize")) document.getElementById("sCrop").value = "maize";

  let farmer = null;
  let seasons = [];
  try {
    farmer = await PandaAPI.farmer(farmerId);
    const plots = await PandaAPI.plots(farmerId);
    document.getElementById("sPlot").innerHTML += PandaUI.options(plots, (p) => p.id, (p) => `${num(p.acres)} acres (added ${date(p.created_at)})`);
    document.getElementById("pageTitle").textContent = staff ? `Seasons & soil: ${farmer.name}` : "Seasons & soil";
  } catch (error) {
    learn.innerHTML = `<h2>Could not load the farmer</h2><p class="muted">${esc(error.message)}</p>`;
    return;
  }

  // ---- What worked before ----
  async function loadHistory() {
    try {
      const h = await PandaAPI.history(farmerId);
      const rows = h.crops.map((c) => {
        const best = c.best;
        return `<tr>
          <td>${PandaUI.cropName(c.crop)}</td>
          <td>${num(c.seasons, 0)}</td>
          <td>${c.avg_yield_kg_per_acre == null ? "—" : num(c.avg_yield_kg_per_acre, 0) + " kg"}</td>
          <td>${best ? `<strong>${num(best.yield_kg_per_acre, 0)} kg/acre</strong> in ${esc(seasonText(best.season))}${
            best.variety ? `<br><span class="small">Variety: ${esc(best.variety)}</span>` : ""}${
            best.methods ? `<br><span class="small muted">${esc(best.methods)}</span>` : ""}` : "—"}</td>
          <td>${c.avg_storage_loss_pct == null ? "—" : `${num(c.avg_storage_loss_pct)}% <span class="muted small">(${num(c.storage_lots, 0)} lots)</span>`}</td></tr>`;
      }).join("");
      const soil = h.latest_soil_test;
      learn.innerHTML = `
        <h2>What worked before</h2>
        ${h.crops.length ? `<div class="table-wrap"><table class="data-table">
          <thead><tr><th>Crop</th><th>Seasons</th><th>Average per acre</th><th>Best season</th><th>Storage loss</th></tr></thead>
          <tbody>${rows}</tbody></table></div>
          <p class="muted small">Per-acre figures use seasons with both acres and harvest entered. Storage loss comes from Hifadhi Mavuno lot records.</p>`
          : `<p class="muted">No seasons recorded yet. Add last season with the form below: what you planted, what you did and what you harvested. After two or three seasons you can compare what worked.</p>`}
        ${soil ? `<h3 style="margin-top:16px">Latest soil test (${date(soil.tested_on)})</h3>
          <ul>${soil.guidance.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>` : ""}`;
    } catch (error) {
      learn.innerHTML = `<h2>What worked before</h2><p class="muted">${esc(error.message)}</p>`;
    }
  }

  // ---- Seasons ----
  const seasonRows = document.getElementById("seasonRows");
  async function loadSeasons() {
    try {
      seasons = await PandaAPI.seasons(farmerId);
      seasonRows.innerHTML = seasons.length ? seasons.map((s) => `<tr>
        <td>${esc(seasonText(s.season))}</td>
        <td>${PandaUI.cropName(s.crop)}${s.variety ? `<br><span class="muted small">${esc(s.variety)}</span>` : ""}</td>
        <td>${s.acres == null ? "—" : num(s.acres)}</td>
        <td>${s.harvest_kg == null ? PandaUI.badge("Not yet", "amber") : num(s.harvest_kg, 0) + " kg"}</td>
        <td>${s.yield_kg_per_acre == null ? "—" : num(s.yield_kg_per_acre, 0) + " kg"}</td>
        <td><button class="button button-outline button-small" style="margin:0" type="button" data-edit="${esc(s.id)}">${s.harvest_kg == null ? "Add harvest" : "Edit"}</button></td>
      </tr>`).join("") : `<tr><td colspan="6" class="empty-row">No seasons yet.</td></tr>`;
    } catch (error) {
      seasonRows.innerHTML = `<tr><td colspan="6" class="empty-row">${esc(error.message)}</td></tr>`;
    }
  }

  const form = document.getElementById("seasonForm");
  const message = document.getElementById("seasonMessage");
  const cancel = document.getElementById("cancelEdit");
  let editing = null;
  const F = (id) => document.getElementById(id);
  function fill(s) {
    F("sSeason").value = s ? s.season : seasonOptions[1];
    F("sCrop").value = s ? s.crop : (crops.some((c) => c.code === "maize") ? "maize" : crops[0].code);
    F("sVariety").value = s ? s.variety : "";
    F("sAcres").value = s && s.acres != null ? s.acres : "";
    F("sPlanted").value = s && s.planted_on ? s.planted_on : "";
    F("sPlot").value = s && s.plot_id ? s.plot_id : "";
    F("sMethods").value = s ? s.methods : "";
    F("sHarvested").value = s && s.harvested_on ? s.harvested_on : "";
    F("sHarvest").value = s && s.harvest_kg != null ? s.harvest_kg : "";
    F("sNotes").value = s ? s.outcome_notes : "";
  }
  function startEdit(id) {
    editing = seasons.find((s) => s.id === id) || null;
    if (!editing) return;
    fill(editing);
    F("seasonFormTitle").textContent = `Edit ${seasonText(editing.season)}`;
    cancel.hidden = false;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
    (editing.harvest_kg == null ? F("sHarvest") : F("sVariety")).focus();
  }
  function stopEdit() {
    editing = null;
    fill(null);
    F("seasonFormTitle").textContent = "Record a season";
    cancel.hidden = true;
  }
  seasonRows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-edit]");
    if (button) startEdit(button.dataset.edit);
  });
  cancel.addEventListener("click", stopEdit);
  fill(null);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    PandaUI.message(message, "");
    const blankToNull = (v) => (v === "" ? null : v);
    const payload = {
      season: F("sSeason").value,
      crop: F("sCrop").value,
      variety: F("sVariety").value.trim(),
      acres: blankToNull(F("sAcres").value),
      planted_on: blankToNull(F("sPlanted").value),
      plot_id: blankToNull(F("sPlot").value),
      methods: F("sMethods").value.trim(),
      harvested_on: blankToNull(F("sHarvested").value),
      harvest_kg: blankToNull(F("sHarvest").value),
      outcome_notes: F("sNotes").value.trim()
    };
    try {
      await PandaUI.busy(form.querySelector("button[type=submit]"), () => editing
        ? PandaAPI.updateSeason(editing.id, payload)
        : PandaAPI.createSeason(farmerId, payload));
      PandaUI.message(message, editing ? "Season updated." : "Season saved.", "success");
      stopEdit();
      await Promise.all([loadSeasons(), loadHistory()]);
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  });

  // ---- Soil tests ----
  const soilList = document.getElementById("soilList");
  async function loadSoil() {
    try {
      const tests = await PandaAPI.soilTests(farmerId);
      soilList.innerHTML = tests.length ? tests.map((t) => `
        <div class="figure" style="margin-bottom:10px">
          <strong style="font-size:16px">${date(t.tested_on)} · ${esc(PandaUI.label(t.source))}</strong>
          <span>pH ${t.ph == null ? "—" : num(t.ph)} · organic carbon ${t.organic_carbon_pct == null ? "—" : num(t.organic_carbon_pct) + "%"}
            · N ${t.nitrogen_pct == null ? "—" : num(t.nitrogen_pct, 3) + "%"} · P ${t.phosphorus_ppm == null ? "—" : num(t.phosphorus_ppm) + " ppm"}
            · K ${t.potassium_ppm == null ? "—" : num(t.potassium_ppm) + " ppm"}</span>
          <ul class="small" style="margin:8px 0 0">${t.guidance.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>
        </div>`).join("") : `<p class="muted">No soil tests yet. A basic test (pH and organic carbon) is a good start.</p>`;
    } catch (error) {
      soilList.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
    }
  }
  const soilForm = document.getElementById("soilForm");
  const soilMessage = document.getElementById("soilMessage");
  // Local date (toISOString would give yesterday's date late at night in Kenya).
  const now = new Date();
  F("tDate").value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  soilForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    PandaUI.message(soilMessage, "");
    const v = (id) => (F(id).value === "" ? null : F(id).value);
    try {
      await PandaUI.busy(soilForm.querySelector("button"), () => PandaAPI.createSoilTest(farmerId, {
        tested_on: F("tDate").value, source: F("tSource").value, ph: v("tPh"),
        organic_carbon_pct: v("tOc"), nitrogen_pct: v("tN"), phosphorus_ppm: v("tP"),
        potassium_ppm: v("tK"), notes: F("tNotes").value.trim()
      }));
      PandaUI.message(soilMessage, "Soil test saved.", "success");
      ["tPh", "tOc", "tN", "tP", "tK", "tNotes"].forEach((id) => { F(id).value = ""; });
      await Promise.all([loadSoil(), loadHistory()]);
    } catch (error) {
      PandaUI.message(soilMessage, error.message);
    }
  });

  await Promise.all([loadHistory(), loadSeasons(), loadSoil()]);
});
