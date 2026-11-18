/*
  index.html: role-aware home page. Every figure comes from the backend.
  Farmers see their own plots and planting plans; staff see their cooperative.
*/
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, date, wardText } = PandaUI;
  const user = await PandaUI.init({ active: "home" });
  const set = (id, value) => { document.getElementById(id).innerHTML = value; };
  const firstName = (user.name || "").split(" ")[0];
  set("welcomeName", firstName ? `, ${esc(firstName)}` : "");
  const status = document.getElementById("dataStatus");
  const stats = (pairs) => pairs.forEach(([value, label], i) => {
    set(`stat${i + 1}`, value);
    set(`stat${i + 1}Label`, esc(label));
  });

  // 7-day forecast for the farmer's ward. Shown only when the backend has a
  // weather source switched on; otherwise nothing is drawn.
  async function showWeather(ward) {
    let data;
    try { data = await PandaAPI.weather(ward.id); } catch { return; }
    if (!data || !data.enabled || !data.days || !data.days.length) return;
    const panel = document.createElement("section");
    panel.className = "panel";
    panel.style.marginTop = "18px";
    panel.innerHTML = `<h2><span class="panel-heading-icon">🌤️</span>Weather: ${esc(ward.name)}, next ${data.days.length} days</h2>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Day</th><th>Rain</th><th>Chance of rain</th><th>Temperature</th></tr></thead>
      <tbody>${data.days.map((d) => `<tr><td>${date(d.date)}</td><td>${num(d.rain_mm, 1)} mm</td>
        <td>${d.rain_chance_pct == null ? "—" : num(d.rain_chance_pct, 0) + "%"}</td>
        <td>${num(d.temp_min_c, 0)}–${num(d.temp_max_c, 0)} °C</td></tr>`).join("")}</tbody></table></div>
      <p class="muted small">${esc(data.attribution || "")}. A forecast, not a guarantee.</p>`;
    document.querySelector(".feature-grid").after(panel);
  }

  if (!PandaUI.isStaff(user)) {
    set("welcomeLine", "Your farm, planting plans and grain records in one place.");
    let farmer = null, plots = [], intents = [];
    try {
      if (user.farmer_id) {
        [farmer, plots, intents] = await Promise.all([
          PandaAPI.farmer(user.farmer_id), PandaAPI.plots(user.farmer_id), PandaAPI.intents()
        ]);
      }
    } catch (error) {
      status.textContent = `Some information could not be loaded: ${error.message}`;
    }
    const acres = plots.reduce((sum, p) => sum + Number(p.acres || 0), 0);
    stats([
      [num(plots.length, 0), "Plots"],
      [`${num(acres)} ac`, "Total land"],
      [num(intents.length, 0), "Planting plans"],
      [farmer && farmer.ward ? esc(farmer.ward.name) : "—", "Ward"]
    ]);
    const latest = intents[0];
    set("panelA", `<h2><span class="panel-heading-icon">❧</span>Planting</h2>
      ${latest ? `<p>Your latest plan: <strong>${num(latest.acres)} acres of ${PandaUI.cropName(latest.crop)}</strong>${
        latest.slot ? `, window ${date(latest.slot.window_start)} – ${date(latest.slot.window_end)}` : ""}.</p>
        ${latest.warning ? `<p class="notice notice-warn">${esc(latest.warning)}</p>` : ""}`
        : `<p class="muted">Get rule-based advice on when to plant, and tell your ward what you plan to grow.</p>`}
      <a class="button button-primary" href="advice.html">Planting advice <span>→</span></a>`);
    if (farmer && farmer.ward) showWeather(farmer.ward);
    set("panelB", `<h2><span class="panel-heading-icon">▣</span>Hifadhi Mavuno: your stored grain</h2>
      <p>When a storage agent records your grain, you receive a private link to check the weight and moisture and to confirm or dispute the record.</p>
      <p class="muted small">View your stored lots, readings, scheduled checks and tamper-evident history here. Your records are read-only; confirmations use the private link from your agent.</p>
      <a class="button button-primary" href="lots.html">View my grain records <span>→</span></a>`);
    set("panelC", `<h2><span class="panel-heading-icon">📍</span>Your farm</h2>
      ${farmer ? `<dl class="kv"><dt>Name</dt><dd>${esc(farmer.name)}</dd><dt>Phone</dt><dd>${esc(farmer.phone)}</dd>
        <dt>Ward</dt><dd>${esc(wardText(farmer.ward))}</dd><dt>Plots</dt><dd>${num(plots.length, 0)} (${num(acres)} acres)</dd></dl>`
        : `<p class="muted">Your login is not linked to a farmer record yet.</p>`}
      <div class="form-actions"><a class="button button-outline" style="margin:0" href="farm.html">Manage plots <span>→</span></a>
        <a class="button button-outline" style="margin:0" href="seasons.html">Seasons &amp; soil <span>→</span></a></div>`);
    set("panelD", `<h2><span class="panel-heading-icon">◷</span>Recent planting plans</h2>
      ${intents.length ? `<ul class="timeline">${intents.slice(0, 4).map((i) => `<li><div class="ev-head">
        <strong>${PandaUI.cropName(i.crop)}</strong><span class="muted small">${date(i.created_at)}</span></div>
        <div class="ev-body">${num(i.acres)} acres</div></li>`).join("")}</ul>`
        : `<p class="muted">No plans yet.</p>`}`);
    if (!status.textContent.startsWith("Some")) status.textContent = "";
    return;
  }

  // ---- Staff: agent, cooperative admin, administrator ----
  set("welcomeLine", `${PandaUI.ROLE_LABELS[user.role]} · your cooperative's farmers and grain lots.`);
  let farmers = [], lots = [], intents = [];
  try {
    [farmers, lots, intents] = await Promise.all([PandaAPI.farmers(), PandaAPI.lots(), PandaAPI.intents()]);
  } catch (error) {
    status.textContent = `Some information could not be loaded: ${error.message}`;
  }
  const stored = lots.filter((l) => l.status === "stored");
  const disputed = lots.filter((l) => l.status === "disputed");
  const storedKg = stored.reduce((sum, l) => sum + Number(l.summary.latest_weight_kg || 0), 0);
  stats([
    [num(farmers.length, 0), "Farmers"],
    [num(stored.length, 0), "Lots in storage"],
    [`${num(storedKg, 0)} kg`, "Grain in storage"],
    [num(disputed.length, 0), "Disputed lots"]
  ]);
  const farmerName = Object.fromEntries(farmers.map((f) => [f.id, f.name]));
  const lotLink = (l) => `<a href="lot.html?id=${encodeURIComponent(l.id)}">${PandaUI.cropName(l.crop)} · ${num(l.initial_weight_kg)} kg</a>`;

  set("panelA", `<h2><span class="panel-heading-icon">⚠</span>Lots needing attention</h2>
    ${disputed.length ? `<ul class="timeline">${disputed.slice(0, 5).map((l) => `<li class="ev-DISPUTED">
      <div class="ev-head"><strong>${lotLink(l)}</strong></div>
      <div class="ev-body">${esc(farmerName[l.farmer_id] || "")} disputed this record</div></li>`).join("")}</ul>`
      : `<p class="muted">No disputed lots.</p>`}`);
  const canWrite = user.role === "agent" || user.role === "admin";
  const canSeeWards = user.role === "coop_admin" || user.role === "admin";
  set("panelB", `<h2><span class="panel-heading-icon">✦</span>Quick actions</h2>
    <div class="form-actions">
      <a class="button button-primary" href="farmers.html">Register a farmer</a>
      ${canWrite ? `<a class="button button-primary" href="lots.html">Register a grain lot</a>` : ""}
      <a class="button button-outline" style="margin:0" href="advice.html">Planting</a>
      ${canSeeWards ? `<a class="button button-outline" style="margin:0" href="wards.html">Ward dashboard</a>` : ""}
    </div>`);
  set("panelC", `<h2><span class="panel-heading-icon">▣</span>Recent lots</h2>
    ${lots.length ? `<ul class="timeline">${lots.slice(0, 4).map((l) => `<li><div class="ev-head"><strong>${lotLink(l)}</strong>
      <span class="muted small">${date(l.registered_at)}</span></div>
      <div class="ev-body">${esc(farmerName[l.farmer_id] || "")} · loss ${num(l.summary.loss_pct)}% ${PandaUI.lotStatusBadge(l.status)}</div></li>`).join("")}</ul>`
      : `<p class="muted">No lots yet.</p>`}
    <a class="button button-outline" href="lots.html">All lots <span>→</span></a>`);
  set("panelD", `<h2><span class="panel-heading-icon">◷</span>Planting plans</h2>
    <p><strong>${num(intents.length, 0)}</strong> plans · <strong>${num(intents.reduce((s, i) => s + Number(i.acres || 0), 0))}</strong> acres planned</p>
    <p class="muted small">${num(intents.filter((i) => i.oversubscribed).length, 0)} were moved to a later window because their crop was above expected demand.</p>
    <a class="button button-outline" href="advice.html">View plans <span>→</span></a>`);
  if (!status.textContent.startsWith("Some")) status.textContent = "";
});
