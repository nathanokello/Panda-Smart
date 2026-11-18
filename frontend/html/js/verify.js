/*
  verify.html?token=<token>: public page the farmer opens from a private link.
  No sign-in. Shows one lot only, and lets the farmer confirm or dispute once.
  Swahili text should be checked by a native speaker before the pilot.
*/
document.addEventListener("DOMContentLoaded", () => {
  const { esc, num, dateTime } = PandaUI;
  const T = {
    en: {
      title: "Confirm your grain record", subtitle: "Hifadhi Mavuno · Panda Smart", loading: "Loading…",
      hello: "Hello", intro: "Your storage agent recorded this grain lot for you. Please check it.",
      crop: "Crop", stored: "Stored", latest: "Latest weight", loss: "Loss", moisture: "Latest moisture",
      history: "History", confirm: "Yes, this is correct", dispute: "No, something is wrong",
      reasonLabel: "Tell us what is wrong", reasonHint: "For example: the weight should be 500 kg.",
      send: "Send", cancel: "Cancel", needReason: "Please say what is wrong.",
      confirmed: "Thank you. Your confirmation has been recorded.",
      disputed: "Thank you. Your concern has been recorded and your cooperative will follow up.",
      already: "You have already responded to this link. Thank you.",
      noToken: "This link is incomplete. Please open the full link you received.",
      expired: "This link has expired. Ask your storage agent for help.",
      notFound: "This link was not found. Check that you opened the full link.",
      error: "Something went wrong. Please try again later.",
      privacy: "Only this one lot is shown. Panda Smart never asks for your PIN or money.",
      ev: { REGISTERED: "Grain stored", MOISTURE_READING: "Moisture reading", WEIGHT_READING: "Weighed",
            CHECKUP: "Check-up", LOSS_RECORDED: "Loss recorded", VERIFIED: "You confirmed",
            DISPUTED: "You disputed", CORRECTION: "Correction" },
      pests: "pests seen", noPests: "no pests seen", bags: "bags", correctedTo: "Corrected to"
    },
    sw: {
      title: "Thibitisha rekodi ya nafaka yako", subtitle: "Hifadhi Mavuno · Panda Smart", loading: "Inapakia…",
      hello: "Habari", intro: "Wakala wako wa hifadhi amerekodi nafaka hii kwa ajili yako. Tafadhali ikague.",
      crop: "Zao", stored: "Iliyohifadhiwa", latest: "Uzito wa mwisho", loss: "Upotevu", moisture: "Unyevu wa mwisho",
      history: "Historia", confirm: "Ndiyo, hii ni sahihi", dispute: "Hapana, kuna kosa",
      reasonLabel: "Tueleze kosa ni nini", reasonHint: "Kwa mfano: uzito unapaswa kuwa kilo 500.",
      send: "Tuma", cancel: "Ghairi", needReason: "Tafadhali eleza kosa ni nini.",
      confirmed: "Asante. Uthibitisho wako umerekodiwa.",
      disputed: "Asante. Malalamiko yako yamerekodiwa na chama chako cha ushirika kitafuatilia.",
      already: "Tayari umejibu kupitia kiungo hiki. Asante.",
      noToken: "Kiungo hiki hakijakamilika. Tafadhali fungua kiungo kamili ulichopokea.",
      expired: "Muda wa kiungo hiki umeisha. Muulize wakala wako wa hifadhi akusaidie.",
      notFound: "Kiungo hiki hakijapatikana. Hakikisha umefungua kiungo kamili.",
      error: "Kuna tatizo. Tafadhali jaribu tena baadaye.",
      privacy: "Ni nafaka hii moja tu inayoonyeshwa. Panda Smart haitakuuliza PIN wala pesa.",
      ev: { REGISTERED: "Nafaka imehifadhiwa", MOISTURE_READING: "Kipimo cha unyevu", WEIGHT_READING: "Imepimwa uzito",
            CHECKUP: "Ukaguzi", LOSS_RECORDED: "Upotevu umerekodiwa", VERIFIED: "Umethibitisha",
            DISPUTED: "Umelalamika", CORRECTION: "Marekebisho" },
      pests: "wadudu wameonekana", noPests: "hakuna wadudu", bags: "magunia", correctedTo: "Imerekebishwa kuwa"
    }
  };
  let lang = localStorage.getItem("panda_lang") === "sw" ? "sw" : "en";
  const t = (key) => T[lang][key];
  const body = document.getElementById("verifyBody");
  const token = PandaUI.param("token");
  let data = null;
  let state = "loading"; // loading | ready | done | error
  let doneKey = "";
  let errorKey = "";

  function staticText() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
    document.getElementById("langSwitch").textContent = lang === "en" ? "Kiswahili" : "English";
    document.title = `${t("title")} | Panda Smart`;
  }

  function eventLine(e) {
    const p = e.payload || {};
    let detail = "";
    if (e.type === "REGISTERED") detail = `${num(p.weight_kg)} kg · ${num(p.bag_count, 0)} ${t("bags")}`;
    else if (e.type === "MOISTURE_READING") detail = `${num(p.moisture_pct)}%`;
    else if (e.type === "WEIGHT_READING") detail = `${num(p.weight_kg)} kg`;
    else if (e.type === "CHECKUP") detail = p.pest_signs ? t("pests") : t("noPests");
    else if (e.type === "LOSS_RECORDED") detail = `${num(p.loss_kg)} kg`;
    else if (e.type === "DISPUTED") detail = `“${esc(p.reason)}”`;
    else if (e.type === "CORRECTION") {
      const np = p.new_payload || {};
      const value = np.weight_kg != null ? `${num(np.weight_kg)} kg` : np.moisture_pct != null ? `${num(np.moisture_pct)}%` : "";
      detail = `${value ? t("correctedTo") + " " + value + ". " : ""}${esc(p.reason || "")}`;
    }
    return `<li><div class="ev-head"><strong>${esc(t("ev")[e.type] || e.type)}</strong>
      <span class="muted small">${dateTime(e.recorded_at)}</span></div>
      ${detail ? `<div class="ev-body">${detail}</div>` : ""}</li>`;
  }

  function render() {
    staticText();
    if (state === "loading") { body.innerHTML = `<p class="muted">${t("loading")}</p>`; return; }
    if (state === "error") { body.innerHTML = `<p class="notice notice-error">${esc(t(errorKey))}</p>`; return; }
    const s = data.summary;
    const responded = data.already_responded || state === "done";
    body.innerHTML = `
      <h2>${t("hello")} ${esc(data.farmer_name)}</h2>
      <p>${t("intro")}</p>
      <dl class="kv" style="margin:14px 0">
        <dt>${t("crop")}</dt><dd>${PandaUI.cropName(data.lot.crop)}</dd>
        <dt>${t("stored")}</dt><dd>${num(s.initial_weight_kg ?? data.lot.initial_weight_kg)} kg</dd>
        <dt>${t("latest")}</dt><dd>${num(s.latest_weight_kg)} kg</dd>
        <dt>${t("loss")}</dt><dd>${num(s.loss_kg)} kg (${num(s.loss_pct)}%)</dd>
        <dt>${t("moisture")}</dt><dd>${s.latest_moisture_pct == null ? "—" : num(s.latest_moisture_pct) + "%"}</dd>
      </dl>
      ${responded
        ? `<p class="notice">${esc(t(doneKey || "already"))}</p>`
        : `<div class="verify-actions" id="actions">
             <button class="button button-primary" id="confirmBtn" type="button">${t("confirm")}</button>
             <button class="button button-outline" style="margin:0" id="disputeBtn" type="button">${t("dispute")}</button>
           </div>
           <form id="disputeForm" hidden style="margin-top:14px">
             <div class="field"><label for="reason">${t("reasonLabel")}</label>
               <textarea id="reason" maxlength="500" placeholder="${esc(t("reasonHint"))}"></textarea></div>
             <p class="form-message" id="verifyMessage" role="alert"></p>
             <div class="verify-actions"><button class="button button-danger" type="submit">${t("send")}</button>
               <button class="button button-outline" style="margin:0" type="button" id="cancelDispute">${t("cancel")}</button></div>
           </form>`}
      <h2 style="margin-top:22px">${t("history")}</h2>
      <ol class="timeline">${data.events.map(eventLine).join("")}</ol>
      <p class="muted small">${t("privacy")}</p>`;
    if (responded) return;
    const actions = document.getElementById("actions");
    const form = document.getElementById("disputeForm");
    document.getElementById("confirmBtn").addEventListener("click", (e) =>
      respond(e.currentTarget, () => PandaAPI.verifyConfirm(token), "confirmed"));
    document.getElementById("disputeBtn").addEventListener("click", () => {
      actions.hidden = true; form.hidden = false; document.getElementById("reason").focus();
    });
    document.getElementById("cancelDispute").addEventListener("click", () => {
      actions.hidden = false; form.hidden = true;
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const reason = document.getElementById("reason").value.trim();
      if (!reason) { PandaUI.message(document.getElementById("verifyMessage"), t("needReason")); return; }
      respond(form.querySelector("button[type=submit]"), () => PandaAPI.verifyDispute(token, reason), "disputed");
    });
  }

  async function respond(button, call, key) {
    try {
      await PandaUI.busy(button, call);
      state = "done"; doneKey = key;
      data = await PandaAPI.verifyData(token).catch(() => data);
    } catch (error) {
      if (error.code === "conflict") { state = "done"; doneKey = "already"; }
      else { state = "error"; errorKey = "error"; }
    }
    render();
  }

  document.getElementById("langSwitch").addEventListener("click", () => {
    lang = lang === "en" ? "sw" : "en";
    localStorage.setItem("panda_lang", lang);
    render();
  });

  async function load() {
    render();
    if (!token) { state = "error"; errorKey = "noToken"; render(); return; }
    try {
      await PandaUI.crops().catch(() => []);
      data = await PandaAPI.verifyData(token);
      state = "ready";
    } catch (error) {
      state = "error";
      errorKey = error.status === 404 ? "notFound" : error.code === "conflict" ? "expired" : "error";
    }
    render();
  }
  load();
});
