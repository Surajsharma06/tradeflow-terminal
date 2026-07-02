import axios from 'axios';

// ── Axios Instance ─────────────────────────────────────────────────────
const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL || ''}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request Interceptor ────────────────────────────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add request timestamp for latency tracking
    config.metadata = { startTime: Date.now() };

    if (import.meta.env.DEV) {
      console.log(
        `%c[API] ${config.method?.toUpperCase()} ${config.url}`,
        'color: #60a5fa; font-weight: bold;',
        config.params || ''
      );
    }

    return config;
  },
  (error) => {
    console.error('[API] Request error:', error);
    return Promise.reject(error);
  }
);

// ── Response Interceptor ───────────────────────────────────────────────
api.interceptors.response.use(
  (response) => {
    const latency = Date.now() - (response.config.metadata?.startTime || Date.now());

    if (import.meta.env.DEV) {
      console.log(
        `%c[API] ✓ ${response.status} ${response.config.url} (${latency}ms)`,
        'color: #34d399; font-weight: bold;'
      );
    }

    // Attach latency to the response for monitoring
    response.latency = latency;

    return response;
  },
  (error) => {
    const { response, config } = error;
    const latency = Date.now() - (config?.metadata?.startTime || Date.now());

    if (response) {
      const status = response.status;

      // Handle 401 — unauthorized
      if (status === 401) {
        localStorage.removeItem('auth_token');
        console.warn('[API] Unauthorized — token cleared');
        // Could dispatch an event or redirect here
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }

      // Handle 429 — rate limited
      if (status === 429) {
        const retryAfter = response.headers['retry-after'];
        console.warn(`[API] Rate limited. Retry after ${retryAfter || '?'}s`);
      }

      // Handle 5xx — server errors
      if (status >= 500) {
        console.error(`[API] Server error ${status} on ${config?.url} (${latency}ms)`);
      }

      console.error(
        `%c[API] ✗ ${status} ${config?.url} (${latency}ms)`,
        'color: #f87171; font-weight: bold;',
        response.data
      );
    } else if (error.code === 'ECONNABORTED') {
      console.error(`[API] ✗ Timeout on ${config?.url} (${latency}ms)`);
    } else {
      console.error('[API] ✗ Network error:', error.message);
    }

    return Promise.reject(error);
  }
);

// ── Market APIs ────────────────────────────────────────────────────────

export const getMarketOverview = (params) =>
  api.get('/market/overview', { params }).then((r) => r.data);

export const getMarketRegime = () =>
  api.get('/market/regime').then((r) => r.data);

export const getMarketBreadth = () =>
  api.get('/market/breadth').then((r) => r.data);

export const getSectorPerformance = () =>
  api.get('/market/sectors').then((r) => r.data);

export const getHeatmap = (params) =>
  api.get('/market/heatmap', { params }).then((r) => r.data);

// ── Signal APIs ────────────────────────────────────────────────────────

export const getSignals = (params) =>
  api.get('/signals/active', { params }).then((r) => r.data);

export const getSignalById = (signalId) =>
  api.get(`/signals/${signalId}`).then((r) => r.data);

export const getSignalHistory = (params) =>
  api.get('/signals/history', { params }).then((r) => r.data);

export const acknowledgeSignal = (signalId, action) =>
  api.post(`/signals/${signalId}/acknowledge`, { action }).then((r) => r.data);

// ── Position APIs ──────────────────────────────────────────────────────

export const getPositions = (params) =>
  api.get('/portfolio/positions', { params }).then((r) => r.data);

export const getPositionById = (positionId) =>
  api.get(`/portfolio/positions/${positionId}`).then((r) => r.data);

export const createPosition = (positionData) =>
  api.post('/portfolio/positions', positionData).then((r) => r.data);

export const updatePosition = (positionId, updates) =>
  api.patch(`/portfolio/positions/${positionId}`, updates).then((r) => r.data);

export const closePosition = (positionId, closeData) =>
  api.post(`/portfolio/positions/${positionId}/close`, closeData).then((r) => r.data);

// ── Portfolio APIs ─────────────────────────────────────────────────────

export const getPortfolioSummary = () =>
  api.get('/portfolio/summary').then((r) => r.data);

export const getEquityCurve = (params) =>
  api.get('/portfolio/equity-curve', { params }).then((r) => r.data);

export const getPnlBreakdown = (params) =>
  api.get('/portfolio/pnl', { params }).then((r) => r.data);

// ── Risk APIs ──────────────────────────────────────────────────────────

export const getRiskStatus = () =>
  api.get('/risk/status').then((r) => r.data);

export const getRiskMetrics = () =>
  api.get('/risk/status').then((r) => r.data);

export const getDrawdownAnalysis = () =>
  api.get('/risk/status').then((r) => r.data);

export const getCorrelations = (params) =>
  api.get('/risk/limits', { params }).then((r) => r.data);

// ── Backtest APIs ──────────────────────────────────────────────────────

export const runBacktest = (config) =>
  api.post('/backtest/run', config).then((r) => r.data);

export const getBacktestResults = () =>
  api.get('/backtest/results').then((r) => r.data);

export const getBacktestHistory = (params) =>
  api.get('/backtest/results', { params }).then((r) => r.data);

// ── Performance APIs ───────────────────────────────────────────────────

export const getPerformance = (params) =>
  api.get('/performance', { params }).then((r) => r.data);

export const getPerformanceByStrategy = (params) =>
  api.get('/performance/strategies', { params }).then((r) => r.data);

export const getMonthlyReturns = (params) =>
  api.get('/performance/monthly', { params }).then((r) => r.data);

// ── Strategy APIs ──────────────────────────────────────────────────────

export const getStrategies = () =>
  api.get('/strategies').then((r) => r.data);

export const getStrategyById = (strategyId) =>
  api.get(`/strategies/${strategyId}`).then((r) => r.data);

export const updateStrategy = (strategyId, config) =>
  api.patch(`/strategies/${strategyId}`, config).then((r) => r.data);

export const toggleStrategy = (strategyId, enabled) =>
  api.post(`/strategies/${strategyId}/toggle`, { enabled }).then((r) => r.data);

// ── Calculator APIs ────────────────────────────────────────────────────

export const calculatePositionSize = (params) =>
  api.post('/tools/position-size', params).then((r) => r.data);

export const calculateCharges = (params) =>
  api.post('/tools/charges', params).then((r) => r.data);

export const calculateRiskReward = (params) =>
  api.post('/tools/position-size', params).then((r) => r.data);

// ── Calendar APIs ──────────────────────────────────────────────────────

export const getCalendar = (params) =>
  api.get('/tools/calendar', { params }).then((r) => r.data);

export const getEarningsCalendar = (params) =>
  api.get('/tools/calendar', { params }).then((r) => r.data);

export const getEconomicEvents = (params) =>
  api.get('/tools/calendar', { params }).then((r) => r.data);

// ── Utility ────────────────────────────────────────────────────────────

export const healthCheck = () =>
  fetch(`${import.meta.env.VITE_API_URL || ''}/health`).then((r) => r.json());

export const getServerTime = () =>
  fetch(`${import.meta.env.VITE_API_URL || ''}/`).then((r) => r.json());

// ── Forex APIs ─────────────────────────────────────────────────────────

export const getForexSignals = (params) =>
  api.get('/signals/forex', { params }).then((r) => r.data);

export const getForexCandles = (params) =>
  api.get('/market/candles', { params }).then((r) => r.data);

// Export the raw axios instance for custom calls
export default api;
