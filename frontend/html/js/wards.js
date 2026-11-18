/* wards.html: ward dashboard for cooperative admins and administrators. */
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, dateTime } = PandaUI;
  await PandaUI.init({ roles: ["coop_admin", "admin"], active: "wards" });
  const rows = document.getElementById("wardRows");
  const detail = document.getElementById("wardDetail");
  const FLAGS = {
    sell_now: ["Sell now", "green"],
    hold: ["Hold", "amber"],
    watch: ["Watch", "blue"]
  };

  async function showWard(id) {
    detail.hidden = false;
    detail.innerHTML = `<p class="muted">Loading…</p>`;
    try {
      const d = await PandaAPI.dashboardWard(id);
      detail.innerHTML = `
        <div class="panel-heading-row"><h2>${esc(d.ward.name)}${d.ward.county ? ", " + esc(d.ward.county) : ""}</h2>
          <span class="muted small">Updated ${dateTime(d.generated_at)}</span></div>
        <div class="table-wrap"><table class="data-table">
          <thead><tr><th>Crop</th><th>Planned acres</th><th>Expected demand</th><th>Above demand</th>
            <th>Stored stock</th><th>Avg. loss</th><th>Price (KES/kg)</th><th>Selling</th></tr></thead>
          <tbody>${d.crops.map((c) => c.suppressed
            ? `<tr><td>${PandaUI.cropName(c.crop)}</td><td colspan="7" class="muted">Hidden: fewer than 5 farmers</td></tr>`
            : `<tr><td>${PandaUI.cropName(c.crop)}</td><td>${num(c.intended_acres)}</td><td>${num(c.expected_demand_acres)}</td>
                <td>${c.oversubscription_pct > 0 ? PandaUI.badge(num(c.oversubscription_pct, 1) + "%", "red") : "—"}</td>
                <td>${num(c.stored_stock_kg)} kg</td><td>${num(c.avg_loss_pct)}%</td><td>${num(c.latest_price_per_kg_kes)}</td>
                <td>${c.sell_flag ? PandaUI.badge(...FLAGS[c.sell_flag] || [c.sell_flag, "grey"]) : "—"}
                  <br><span class="muted small">${esc(c.sell_flag_reason)}</span></td></tr>`).join("")}
          </tbody></table></div>
        <p class="muted small">"Above demand" is how far planned acres exceed expected demand. The selling flag compares the latest price with the 3-month average; it is a prompt, not financial advice.</p>`;
      detail.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      detail.innerHTML = `<p class="muted">${esc(error.message)}</p>`;
    }
  }

  try {
    const wards = await PandaAPI.dashboardWards();
    rows.innerHTML = wards.length ? wards.map((w) => `
      <tr class="clickable" data-id="${esc(w.id)}"><td><a href="#ward-${esc(w.id)}">${esc(w.name)}</a></td>
        <td>${esc(w.county)}</td><td>${num(w.crop_count, 0)}</td><td>${num(w.total_intended_acres)}</td>
        <td>${num(w.stored_stock_kg)} kg</td></tr>`).join("")
      : `<tr><td colspan="5" class="empty-row">No wards yet.</td></tr>`;
    rows.addEventListener("click", (event) => {
      const row = event.target.closest("tr[data-id]");
      if (!row) return;
      event.preventDefault();
      showWard(row.dataset.id);
    });
    if (wards.length) showWard(wards[0].id);
  } catch (error) {
    rows.innerHTML = `<tr><td colspan="5" class="empty-row">${esc(error.message)}</td></tr>`;
  }
});
