/*
  Shared API client. Every page uses this, so the token header, the error
  envelope and paging are handled in one place.

  Backend error shape (all non-2xx): {"error": {"code", "message", "fields"}}
*/
(function () {
  const config = window.PANDA_CONFIG;
  const tokenKey = "panda_smart_token";
  const userKey = "panda_smart_user";

  function url(path) {
    if (/^https?:\/\//.test(path)) return path; // "next" links from paged lists
    return config.API_BASE_URL.replace(/\/$/, "") + config.API_PREFIX + path;
  }

  class ApiError extends Error {
    constructor(message, status, code, fields) {
      super(message);
      this.status = status;
      this.code = code;
      this.fields = fields || {};
    }
  }

  function messageFrom(body, status) {
    if (body && body.error) {
      const fields = body.error.fields || {};
      const fieldText = Object.entries(fields)
        .filter(([key]) => key !== "non_field_errors" && key !== "detail")
        .map(([key, list]) => `${key.replace(/_/g, " ")}: ${[].concat(list).join(" ")}`);
      // Show the field-level reasons when there are several.
      if (fieldText.length > 1) return fieldText.join(" · ");
      return body.error.message || fieldText.join(" ") || `Request failed (${status})`;
    }
    if (body && body.detail) return body.detail;
    if (status === 0) return "Cannot reach the Panda Smart server. Check that Django is running.";
    return `Request failed (${status})`;
  }

  async function request(path, options = {}) {
    const { method = "GET", body, query, auth = true } = options;
    let target = url(path);
    if (query) {
      const params = new URLSearchParams();
      Object.entries(query).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") params.set(k, v);
      });
      const qs = params.toString();
      if (qs) target += (target.includes("?") ? "&" : "?") + qs;
    }
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const token = localStorage.getItem(tokenKey);
    // Public endpoints (verify, wards) are called without the token.
    if (auth && token) headers.Authorization = `Token ${token}`;

    let response;
    try {
      response = await fetch(target, {
        method, headers, body: body === undefined ? undefined : JSON.stringify(body)
      });
    } catch (networkError) {
      throw new ApiError(messageFrom(null, 0), 0, "network_error");
    }
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const err = new ApiError(
        messageFrom(data, response.status), response.status,
        data && data.error ? data.error.code : "error",
        data && data.error ? data.error.fields : {}
      );
      if (response.status === 401 && auth && token) {
        // Token expired or revoked: clear it and send the user to sign in.
        clearSession();
        if (!/login\.html$/.test(location.pathname)) {
          location.href = "login.html?expired=1";
        }
      }
      throw err;
    }
    return data;
  }

  // Lists are paged ({count, next, previous, results}). This follows "next"
  // so drop-downs see every record, up to a safety limit.
  async function listAll(path, options = {}) {
    const results = [];
    let next = path;
    let query = { limit: 100, ...(options.query || {}) };
    let guard = 0;
    while (next && guard < 50) {
      const page = await request(next, { ...options, query });
      if (Array.isArray(page)) return page;
      results.push(...(page.results || []));
      next = page.next;
      query = null; // "next" already carries limit and offset
      guard += 1;
    }
    return results;
  }

  function clearSession() {
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(userKey);
  }

  const E = config.ENDPOINTS;
  window.PandaAPI = {
    ApiError,
    request,
    listAll,
    getToken: () => localStorage.getItem(tokenKey),
    saveSession(token, user) {
      localStorage.setItem(tokenKey, token);
      if (user) localStorage.setItem(userKey, JSON.stringify(user));
    },
    cachedUser() {
      try { return JSON.parse(localStorage.getItem(userKey) || "null"); } catch { return null; }
    },
    clearSession,
    async logout() {
      try { await request(E.logout, { method: "POST" }); } catch { /* still sign out locally */ }
      clearSession();
    },

    login: (payload) => request(E.login, { method: "POST", body: payload, auth: false }),
    registerFarmer: (payload) => request(E.farmerRegister, { method: "POST", body: payload, auth: false }),
    me: () => request(E.currentUser),

    wards: () => listAll(E.wards, { auth: false }),
    crops: () => listAll(E.crops, { auth: false }),

    farmers: () => listAll(E.farmers),
    farmer: (id) => request(E.farmer(id)),
    createFarmer: (payload) => request(E.farmers, { method: "POST", body: payload }),
    plots: (farmerId) => listAll(E.plots(farmerId)),
    createPlot: (farmerId, payload) => request(E.plots(farmerId), { method: "POST", body: payload }),

    seasons: (farmerId) => listAll(E.seasons(farmerId)),
    createSeason: (farmerId, payload) => request(E.seasons(farmerId), { method: "POST", body: payload }),
    updateSeason: (id, payload) => request(E.season(id), { method: "PATCH", body: payload }),
    soilTests: (farmerId) => listAll(E.soilTests(farmerId)),
    createSoilTest: (farmerId, payload) => request(E.soilTests(farmerId), { method: "POST", body: payload }),
    history: (farmerId) => request(E.history(farmerId)),

    lots: (query) => listAll(E.lots, { query }),
    lot: (id) => request(E.lot(id)),
    createLot: (payload) => request(E.lots, { method: "POST", body: payload }),
    lotEvents: (id) => listAll(E.lotEvents(id)),
    addEvent: (id, type, payload) => request(E.lotEvents(id), { method: "POST", body: { type, payload } }),
    verifyChain: (id) => request(E.verifyChain(id)),

    verifyData: (token) => request(E.verify(token), { auth: false }),
    verifyConfirm: (token) => request(E.verifyConfirm(token), { method: "POST", body: {}, auth: false }),
    verifyDispute: (token, reason) => request(E.verifyDispute(token), { method: "POST", body: { reason }, auth: false }),

    advice: (ward, crop) => request(E.advice, { query: { ward, crop } }),
    intents: (query) => listAll(E.plantingIntents, { query }),
    createIntent: (payload) => request(E.plantingIntents, { method: "POST", body: payload }),
    weather: (wardId) => request(E.wardWeather(wardId)),
    slots: (wardId, crop, season) => request(E.wardSlots(wardId), { query: { crop, season } }),

    users: () => listAll(E.users),
    createUser: (payload) => request(E.users, { method: "POST", body: payload }),
    updateUser: (id, payload) => request(E.user(id), { method: "PATCH", body: payload }),
    tenants: () => listAll(E.tenants),

    dashboardWards: () => request(E.dashboardWards),
    dashboardWard: (id) => request(E.dashboardWard(id)),

    marketplace: (query) => listAll(E.marketplace, { auth: false, query }),
    createListing: (payload) => request(E.marketplace, { method: "POST", body: payload }),
    updateListingStatus: (id, status) => request(E.marketplaceStatus(id), { method: "PATCH", body: { status } })
  };
})();
