/*
  PANDA SMART FRONTEND CONFIGURATION
  API_BASE_URL is where Django runs. Local default: http://127.0.0.1:8000
  Every path below exists in the backend (see ../../architecture.md, Section 6).
*/
window.PANDA_CONFIG = {
  API_BASE_URL: "http://127.0.0.1:8000",
  API_PREFIX: "/api/v1",
  ENDPOINTS: {
    login: "/auth/login/",
    logout: "/auth/logout/",
    currentUser: "/auth/me/",
    farmerRegister: "/auth/register/farmer/",
    wards: "/wards/",
    crops: "/crops/",
    farmers: "/farmers/",
    farmer: (id) => `/farmers/${id}/`,
    plots: (farmerId) => `/farmers/${farmerId}/plots/`,
    seasons: (farmerId) => `/farmers/${farmerId}/seasons/`,
    season: (id) => `/seasons/${id}/`,
    soilTests: (farmerId) => `/farmers/${farmerId}/soil-tests/`,
    history: (farmerId) => `/farmers/${farmerId}/history/`,
    lots: "/lots/",
    lot: (id) => `/lots/${id}/`,
    lotEvents: (id) => `/lots/${id}/events/`,
    verifyChain: (id) => `/lots/${id}/verify-chain/`,
    verify: (token) => `/verify/${encodeURIComponent(token)}/`,
    verifyConfirm: (token) => `/verify/${encodeURIComponent(token)}/confirm/`,
    verifyDispute: (token) => `/verify/${encodeURIComponent(token)}/dispute/`,
    advice: "/advice/",
    plantingIntents: "/planting-intents/",
    wardSlots: (wardId) => `/wards/${wardId}/slots/`,
    wardWeather: (wardId) => `/wards/${wardId}/weather/`,
    users: "/users/",
    user: (id) => `/users/${id}/`,
    tenants: "/tenants/",
    dashboardWards: "/dashboard/wards/",
    dashboardWard: (id) => `/dashboard/wards/${id}/`,
    marketplace: "/marketplace/",
    marketplaceStatus: (id) => `/marketplace/${id}/`
  },
  // Season used by the backend's demo data (planting/services.py DEFAULT_SEASON).
  DEFAULT_SEASON: "2026-short-rains"
};
