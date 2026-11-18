/*
  lot.html?id=<lot id>: one grain lot.
  - Loss figure shown WITH its formula (architecture.md 7.4).
  - History is read-only. Mistakes are fixed with a CORRECTION entry.
  - Farmer verification state and link.
*/
document.addEventListener("DOMContentLoaded", async () => {
  const { esc, num, dateTime, label } = PandaUI;
  const user = await PandaUI.init({ roles: ["farmer", ...PandaUI.STAFF], active: "lots" });
  const canWrite = user.role === "agent" || user.role === "admin";
  const lotId = PandaUI.param("id");
  const header = document.getElementById("lotHeader");
  if (!lotId) {
    header.innerHTML = `<h2>No lot selected</h2><p><a href="lots.html">Back to the lot list</a></p>`;
    return;
  }

  const METHOD = (m) => label(m);
  let lot = null;
  let events = [];

  function correctedMap() {
    const map = {};
    events.filter((e) => e.type === "CORRECTION").forEach((e) => {
      map[e.payload.corrects_event_id] = e;
    });
    return map;
  }

  function describe(event, bySeq) {
    const p = event.payload || {};
    switch (event.type) {
      case "REGISTERED":
        return `${num(p.weight_kg)} kg in ${num(p.bag_count, 0)} bags · ${esc(METHOD(p.storage_method))}${
          p.moisture_pct == null ? "" : ` · Initial moisture ${num(p.moisture_pct)}%`
        }`;
      case "MOISTURE_READING": return `Moisture ${num(p.moisture_pct)}%`;
      case "WEIGHT_READING": return `Weight ${num(p.weight_kg)} kg`;
      case "CHECKUP":
        return `Pests seen: <strong>${p.pest_signs ? "yes" : "no"}</strong>${
          p.good_weight_kg == null ? "" : ` · Weight ${num(p.good_weight_kg)} kg`
        }${p.moisture_pct == null ? "" : ` · Moisture ${num(p.moisture_pct)}%`}${
          p.notes ? " · " + esc(p.notes) : ""
        }`;
      case "SYSTEM_DECISION":
        return `${esc(p.decision || "Moisture status updated")}${
          p.moisture_pct == null ? "" : ` · ${num(p.moisture_pct)}% moisture`
        }${p.limit_pct == null ? "" : ` · limit ${num(p.limit_pct)}%`}`;
      case "LOSS_RECORDED": return `${num(p.loss_kg)} kg lost · cause: ${esc(p.cause)}`;
      case "VERIFIED": return `Farmer confirmed this record (${esc(p.method || "link")})`;
      case "DISPUTED": return `Farmer disputed this record: “${esc(p.reason)}”`;
      case "CORRECTION": {
        const target = bySeq[p.corrects_event_id];
        const changes = Object.entries(p.new_payload || {})
          .map(([k, v]) => `${esc(label(k))} → ${esc(v)}`).join(", ");
        return `Corrects entry #${target ? target.sequence : "?"}: ${changes}. Reason: ${esc(p.reason)}`;
      }
      default: return esc(JSON.stringify(p));
    }
  }

  function renderHeader(farmer) {
    const state = PandaUI.verifyState(events);
    document.getElementById("pageTitle").textContent = "Grain lot";
    header.innerHTML = `
      <div class="panel-heading-row"><h2>${PandaUI.cropName(lot.crop)} · ${num(lot.initial_weight_kg)} kg</h2>
        <div>${PandaUI.lotStatusBadge(lot.status)} ${state.html}</div></div>
      <dl class="kv">
        <dt>Farmer</dt><dd>${farmer ? `<a href="farm.html?farmer=${encodeURIComponent(farmer.id)}">${esc(farmer.name)}</a> · ${esc(farmer.phone)}` : "—"}</dd>
        <dt>Stored at</dt><dd>${esc(lot.location_label)}</dd>
        <dt>Registered</dt><dd>${dateTime(lot.registered_at)} by ${esc(lot.agent ? lot.agent.name : "—")}</dd>
        <dt>Lot ID</dt><dd class="small" style="font-weight:400;word-break:break-all">${esc(lot.id)}</dd>
      </dl>
      ${user.role === "farmer" ? `<p class="notice">This is your read-only storage record. To confirm or dispute it, use the private verification link sent by your storage agent.</p>` : ""}
      <div class="form-actions no-print"><button class="button button-outline button-small" style="margin:0" type="button" onclick="window.print()">Print record</button></div>`;
  }

  function renderLoss() {
    const s = lot.summary;
    const recorded = events.filter((e) => e.type === "LOSS_RECORDED")
      .reduce((sum, e) => sum + Number(e.payload.loss_kg || 0), 0);
    const corrected = Object.keys(correctedMap()).length;
    const moistureStatus = {
      unknown: "Guideline not confirmed",
      dry: "Dry enough",
      retest: "Re-test needed",
      officer: "Extension officer needed"
    }[lot.moisture_status] || PandaUI.label(lot.moisture_status);
    const followUps = lot.follow_ups || [];
    document.getElementById("lossPanel").innerHTML = `
      <h2>Weight and loss</h2>
      <div class="figure-row">
        <div class="figure"><strong>${num(s.initial_weight_kg ?? lot.initial_weight_kg)} kg</strong><span>Stored</span></div>
        <div class="figure"><strong>${num(s.latest_weight_kg)} kg</strong><span>Latest weighing</span></div>
        <div class="figure"><strong>${num(s.loss_kg)} kg</strong><span>Loss (${num(s.loss_pct)}%)</span></div>
        <div class="figure"><strong>${s.latest_moisture_pct == null ? "—" : num(s.latest_moisture_pct) + "%"}</strong><span>Latest moisture</span></div>
        <div class="figure"><strong>${s.dry_matter_loss_kg == null ? "—" : `${num(s.dry_matter_loss_kg)} kg`}</strong><span>Estimated dry-matter loss</span></div>
      </div>
      <div class="formula">Loss = stored weight − latest weighing<br>
        &nbsp;&nbsp;&nbsp;&nbsp; = ${num(s.initial_weight_kg ?? lot.initial_weight_kg)} kg − ${num(s.latest_weight_kg)} kg = ${num(s.loss_kg)} kg<br>
        Loss % = ${num(s.loss_kg)} ÷ ${num(s.initial_weight_kg ?? lot.initial_weight_kg)} × 100 = ${num(s.loss_pct)}%</div>
      <p class="muted small">This is a plain weight difference. It is not adjusted for moisture, so grain drying out also shows as loss.
        ${s.dry_matter_loss_kg == null
          ? " Dry-matter loss is unavailable until both registration-time and current moisture readings are recorded."
          : ` Estimated dry-matter loss compares ${num(s.initial_dry_matter_kg)} kg initially with ${num(s.dry_matter_latest_weight_kg)} kg now (${num(s.dry_matter_loss_pct)}%).`}
        ${corrected ? ` Corrections are applied (${corrected} ${corrected === 1 ? "entry" : "entries"} corrected).` : ""}
        ${recorded ? ` Losses recorded with a cause total ${num(recorded)} kg; they are listed in the history and are not added to the figure above.` : ""}</p>`;
    document.getElementById("lossPanel").insertAdjacentHTML("beforeend", `
      <h3>Moisture monitoring</h3>
      <p>${PandaUI.badge(moistureStatus, lot.moisture_status === "dry" ? "green" : lot.moisture_status === "retest" || lot.moisture_status === "officer" ? "amber" : "grey")}
        ${lot.moisture_limit_pct == null ? `<span class="muted small">No crop-specific moisture threshold is configured.</span>`
          : `<span class="muted small">Configured maize guidance: ${num(lot.moisture_limit_pct)}% maximum (confirm with an agronomist).</span>`}</p>
      <p class="small">Re-tests recorded: ${num(lot.retest_count, 0)} · Next check: ${lot.next_check_at ? dateTime(lot.next_check_at) : "—"}</p>
      <h3>Scheduled storage checks</h3>
      ${followUps.length ? `<ul class="timeline">${followUps.map((check) => `<li>
        <div class="ev-head"><strong>${esc(PandaUI.label(check.kind))}</strong>
          <span class="muted small">${check.completed_at ? `Completed ${dateTime(check.completed_at)}` : `Due ${dateTime(check.due_at)}`}</span></div>
        <div class="ev-body">${check.good_weight_kg == null ? "" : `Weight ${num(check.good_weight_kg)} kg`}
          ${check.moisture_pct == null ? "" : ` · Moisture ${num(check.moisture_pct)}%`}
          ${check.pests == null ? "" : ` · Pests ${check.pests ? "reported" : "not seen"}`}</div>
      </li>`).join("")}</ul>` : `<p class="muted small">No scheduled storage checks.</p>`}`);
  }

  function renderTimeline() {
    const byId = Object.fromEntries(events.map((e) => [e.id, e]));
    const corrections = correctedMap();
    document.getElementById("timeline").innerHTML = events.map((e) => `
      <li class="ev-${esc(e.type)}">
        <div class="ev-head"><strong>#${e.sequence} ${esc(label(e.type.toLowerCase()))}</strong>
          <span class="muted small">${dateTime(e.recorded_at)}</span>
          ${corrections[e.id] ? PandaUI.badge(`Corrected in #${corrections[e.id].sequence}`, "amber") : ""}</div>
        <div class="ev-body">${describe(e, byId)}</div>
        <div class="ev-meta">By ${esc(e.type === "SYSTEM_DECISION" ? "system" : e.recorded_by ? e.recorded_by.name : "farmer (link)")} · fingerprint ${esc((e.hash || "").slice(0, 16))}…</div>
      </li>`).join("") || `<li>No entries.</li>`;
  }

  function renderLink() {
    const panel = document.getElementById("linkPanel");
    const state = PandaUI.verifyState(events);
    if (user.role === "farmer") {
      panel.innerHTML = `<h2>Farmer confirmation</h2><p>${state.html}</p>
        <p class="small muted">Confirmation is submitted through the private verification link sent by your storage agent.</p>`;
      return;
    }
    if (!lot.verification_url) {
      panel.innerHTML = `<h2>Farmer confirmation</h2><p class="muted">No verification link exists for this lot.</p>`;
      return;
    }
    panel.innerHTML = `
      <h2>Farmer confirmation</h2>
      <p>${state.html}</p>
      ${state.key === "awaiting" ? `
        <p class="small">Send this private link to the farmer. They can confirm or dispute the record without signing in. It works once and expires after 14 days.</p>
        <div class="copy-row"><input id="verifyLink" readonly value="${esc(lot.verification_url)}" aria-label="Verification link">
          <button class="button button-primary button-small" id="copyLink" type="button">Copy</button></div>
        <p class="hint muted small">Sending the link by SMS is planned (Africa's Talking) and not connected yet.</p>`
        : `<p class="small muted">The farmer has already responded. The link cannot be used again.</p>`}`;
    const copy = document.getElementById("copyLink");
    if (copy) copy.addEventListener("click", async () => {
      const input = document.getElementById("verifyLink");
      try { await navigator.clipboard.writeText(input.value); copy.textContent = "Copied"; }
      catch { input.select(); document.execCommand("copy"); copy.textContent = "Copied"; }
    });
  }

  async function load() {
    try {
      [lot, events] = await Promise.all([PandaAPI.lot(lotId), PandaAPI.lotEvents(lotId)]);
    } catch (error) {
      header.innerHTML = `<h2>Could not load this lot</h2><p class="muted">${esc(error.message)}</p>`;
      return false;
    }
    let farmer = null;
    try { farmer = await PandaAPI.farmer(lot.farmer_id); } catch { /* shown as — */ }
    renderHeader(farmer);
    renderLoss();
    renderTimeline();
    renderLink();
    refreshCorrectionTargets();
    return true;
  }

  // ---- Add a record ----
  const typeSelect = document.getElementById("eType");
  const fields = document.getElementById("eFields");
  const FIELD_HTML = {
    MOISTURE_READING: `<div class="field full"><label for="fMoisture">Moisture (%)</label><input id="fMoisture" type="number" min="0" max="100" step="0.1" required></div>`,
    WEIGHT_READING: `<div class="field full"><label for="fWeight">Weight now (kg)</label><input id="fWeight" type="number" min="0" step="0.01" required></div>`,
    CHECKUP: `<label class="check-row full"><input type="checkbox" id="fPests"><span>Signs of pests (weevils, larger grain borer, moulds)</span></label>
      <div class="field"><label for="fCheckWeight">Good weight (kg), if measured</label><input id="fCheckWeight" type="number" min="0" step="0.01"></div>
      <div class="field"><label for="fCheckMoisture">Moisture (%), if measured</label><input id="fCheckMoisture" type="number" min="0" max="100" step="0.1"></div>
      <div class="field full"><label for="fNotes">Notes</label><textarea id="fNotes" maxlength="500"></textarea></div>`,
    LOSS_RECORDED: `<div class="field"><label for="fLoss">Loss (kg)</label><input id="fLoss" type="number" min="0" step="0.01" required></div>
      <div class="field"><label for="fCause">Cause</label><select id="fCause" required>
        <option value="pests">Pests</option><option value="moisture_mould">Moisture / mould</option><option value="rodents">Rodents</option>
        <option value="spillage">Spillage</option><option value="theft">Theft</option><option value="other">Other</option></select></div>`,
    CORRECTION: `<div class="field full"><label for="fTarget">Entry to correct</label><select id="fTarget" required></select></div>
      <div class="field full"><label for="fNewValue" id="fNewLabel">Correct value</label><input id="fNewValue" type="number" min="0" step="0.01" required></div>
      <div class="field full"><label for="fReason">Reason</label><input id="fReason" required maxlength="300" placeholder="e.g. Typed 49.2 instead of 492"></div>
      <p class="hint full muted small">The original entry stays in the history. Weight and moisture entries can be corrected here.</p>`
  };
  const CORRECTABLE = {
    REGISTERED: { weight_kg: "weight", moisture_pct: "moisture" },
    WEIGHT_READING: { weight_kg: "weight" },
    MOISTURE_READING: { moisture_pct: "moisture" },
    CHECKUP: { good_weight_kg: "weight", moisture_pct: "moisture" }
  };

  function refreshCorrectionTargets() {
    const target = document.getElementById("fTarget");
    if (!target) return;
    const list = events.flatMap((e) => Object.entries(CORRECTABLE[e.type] || {})
      .filter(([key]) => e.payload[key] != null)
      .map(([key, kind]) => ({ event: e, key, kind })));
    target.innerHTML = list.map(({ event: e, key, kind }) =>
      `<option value="${esc(e.id)}|${esc(key)}">#${e.sequence} ${esc(label(e.type.toLowerCase()))}: ${
        num(e.payload[key])}${kind === "moisture" ? "%" : " kg"}</option>`).join("");
    const update = () => {
      const [, key] = target.value.split("|");
      const moisture = key === "moisture_pct";
      document.getElementById("fNewLabel").textContent = moisture ? "Correct moisture (%)" : "Correct weight (kg)";
      document.getElementById("fNewValue").max = moisture ? "100" : "";
    };
    target.onchange = update;
    update();
  }
  function showFields() {
    fields.innerHTML = FIELD_HTML[typeSelect.value];
    if (typeSelect.value === "CORRECTION") refreshCorrectionTargets();
  }
  typeSelect.addEventListener("change", showFields);

  function payloadFor(type) {
    const v = (id) => document.getElementById(id).value;
    switch (type) {
      case "MOISTURE_READING": return { moisture_pct: Number(v("fMoisture")) };
      case "WEIGHT_READING": return { weight_kg: Number(v("fWeight")) };
      case "CHECKUP": {
        const weight = v("fCheckWeight");
        const moisture = v("fCheckMoisture");
        return {
          pest_signs: document.getElementById("fPests").checked,
          notes: v("fNotes").trim(),
          ...(weight === "" ? {} : { good_weight_kg: Number(weight) }),
          ...(moisture === "" ? {} : { moisture_pct: Number(moisture) })
        };
      }
      case "LOSS_RECORDED": return { loss_kg: Number(v("fLoss")), cause: v("fCause") };
      case "CORRECTION": {
        const [eventId, key] = v("fTarget").split("|");
        const ev = events.find((e) => e.id === eventId);
        if (!ev) throw new Error("Choose the entry to correct.");
        return { corrects_event_id: ev.id, new_payload: { [key]: Number(v("fNewValue")) }, reason: v("fReason").trim() };
      }
      default: return {};
    }
  }

  if (!(await load())) return;
  if (canWrite) {
    document.getElementById("eventPanel").hidden = false;
    showFields();
    const form = document.getElementById("eventForm");
    const message = document.getElementById("eventMessage");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      PandaUI.message(message, "");
      try {
        const type = typeSelect.value;
        const payload = payloadFor(type);
        await PandaUI.busy(form.querySelector("button[type=submit]"), () => PandaAPI.addEvent(lotId, type, payload));
        PandaUI.message(message, "Saved.", "success");
        showFields();
        await load();
      } catch (error) {
        PandaUI.message(message, error.message);
      }
    });
  }
  if (PandaUI.param("new")) {
    PandaUI.message(document.getElementById("chainMessage"), "Lot registered. Copy the link on the right and send it to the farmer.", "success");
  }

  const chainMessage = document.getElementById("chainMessage");
  document.getElementById("chainButton").addEventListener("click", async (event) => {
    try {
      const result = await PandaUI.busy(event.currentTarget, () => PandaAPI.verifyChain(lotId));
      PandaUI.message(chainMessage, result.valid
        ? "Record intact: every entry matches its fingerprint and the order is unbroken."
        : "Warning: the record does not match its fingerprints. Report this to an administrator.",
        result.valid ? "success" : "error");
    } catch (error) {
      PandaUI.message(chainMessage, error.message);
    }
  });
});
