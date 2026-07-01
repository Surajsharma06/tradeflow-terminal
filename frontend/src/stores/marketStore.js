import { create } from 'zustand';

const useMarketStore = create((set, get) => ({
  // ── Indices ──────────────────────────────────────────────────────────
  indices: {
    NIFTY: {
      name: 'NIFTY 50',
      value: 24856.75,
      change: 187.40,
      changePercent: 0.76,
      open: 24669.35,
      high: 24892.10,
      low: 24631.50,
      prevClose: 24669.35,
      timestamp: Date.now(),
    },
    SENSEX: {
      name: 'SENSEX',
      value: 81742.30,
      change: 548.65,
      changePercent: 0.68,
      open: 81193.65,
      high: 81890.20,
      low: 81045.80,
      prevClose: 81193.65,
      timestamp: Date.now(),
    },
    BANKNIFTY: {
      name: 'BANK NIFTY',
      value: 53472.85,
      change: -124.30,
      changePercent: -0.23,
      open: 53597.15,
      high: 53720.40,
      low: 53310.60,
      prevClose: 53597.15,
      timestamp: Date.now(),
    },
    NIFTYIT: {
      name: 'NIFTY IT',
      value: 38245.60,
      change: 312.80,
      changePercent: 0.82,
      open: 37932.80,
      high: 38310.45,
      low: 37890.20,
      prevClose: 37932.80,
      timestamp: Date.now(),
    },
    SP500: {
      name: 'S&P 500',
      value: 5321.48,
      change: 24.67,
      changePercent: 0.47,
      open: 5296.81,
      high: 5334.20,
      low: 5289.15,
      prevClose: 5296.81,
      timestamp: Date.now(),
      currency: 'USD',
    },
    NASDAQ: {
      name: 'NASDAQ',
      value: 16742.39,
      change: 108.52,
      changePercent: 0.65,
      open: 16633.87,
      high: 16798.45,
      low: 16601.30,
      prevClose: 16633.87,
      timestamp: Date.now(),
      currency: 'USD',
    },
    DOWJONES: {
      name: 'DOW JONES',
      value: 39148.60,
      change: -52.30,
      changePercent: -0.13,
      open: 39200.90,
      high: 39285.70,
      low: 39072.15,
      prevClose: 39200.90,
      timestamp: Date.now(),
      currency: 'USD',
    },
    BTC: {
      name: 'Bitcoin',
      value: 67842.50,
      change: 1247.30,
      changePercent: 1.87,
      open: 66595.20,
      high: 68120.80,
      low: 66310.40,
      prevClose: 66595.20,
      timestamp: Date.now(),
      currency: 'USD',
    },
    ETH: {
      name: 'Ethereum',
      value: 3742.18,
      change: 84.62,
      changePercent: 2.31,
      open: 3657.56,
      high: 3780.90,
      low: 3640.25,
      prevClose: 3657.56,
      timestamp: Date.now(),
      currency: 'USD',
    },
  },

  // ── Live Prices Map ──────────────────────────────────────────────────
  prices: {
    RELIANCE: { ltp: 2892.45, change: 34.20, changePercent: 1.20, bid: 2892.00, ask: 2892.90, volume: 4823150, high: 2905.30, low: 2851.10 },
    TCS: { ltp: 4185.30, change: -24.70, changePercent: -0.59, bid: 4184.80, ask: 4185.80, volume: 1247830, high: 4220.50, low: 4165.00 },
    HDFCBANK: { ltp: 1847.65, change: 18.40, changePercent: 1.01, bid: 1847.20, ask: 1848.10, volume: 3562470, high: 1858.90, low: 1825.30 },
    INFY: { ltp: 1912.80, change: 22.80, changePercent: 1.21, bid: 1912.30, ask: 1913.30, volume: 2891560, high: 1925.40, low: 1886.50 },
    ICICIBANK: { ltp: 1178.35, change: -8.15, changePercent: -0.69, bid: 1178.00, ask: 1178.70, volume: 5124380, high: 1192.60, low: 1172.40 },
    WIPRO: { ltp: 478.90, change: 6.35, changePercent: 1.34, bid: 478.60, ask: 479.20, volume: 3847920, high: 482.70, low: 471.80 },
    SBIN: { ltp: 824.55, change: 12.90, changePercent: 1.59, bid: 824.20, ask: 824.90, volume: 8234510, high: 831.20, low: 810.40 },
    TATAMOTORS: { ltp: 972.40, change: -15.60, changePercent: -1.58, bid: 972.00, ask: 972.80, volume: 6912340, high: 992.30, low: 968.50 },
    LT: { ltp: 3542.10, change: 45.80, changePercent: 1.31, bid: 3541.60, ask: 3542.60, volume: 1523470, high: 3568.90, low: 3492.30 },
    AXISBANK: { ltp: 1156.75, change: 9.25, changePercent: 0.81, bid: 1156.30, ask: 1157.20, volume: 4267890, high: 1164.50, low: 1144.80 },
    BHARTIARTL: { ltp: 1624.30, change: 28.70, changePercent: 1.80, bid: 1623.80, ask: 1624.80, volume: 2345670, high: 1638.90, low: 1592.40 },
    MARUTI: { ltp: 12478.50, change: -142.30, changePercent: -1.13, bid: 12476.00, ask: 12481.00, volume: 412890, high: 12650.80, low: 12420.10 },
    ADANIENT: { ltp: 3124.85, change: 67.45, changePercent: 2.20, bid: 3124.30, ask: 3125.40, volume: 3891240, high: 3148.70, low: 3045.20 },
    HCLTECH: { ltp: 1678.90, change: 14.60, changePercent: 0.88, bid: 1678.40, ask: 1679.40, volume: 1892340, high: 1692.30, low: 1661.50 },
    SUNPHARMA: { ltp: 1542.35, change: -18.90, changePercent: -1.21, bid: 1542.00, ask: 1542.70, volume: 2134560, high: 1568.40, low: 1535.80 },
  },

  // ── Market Regime ────────────────────────────────────────────────────
  marketRegime: 'BULL_TRENDING',
  regimeConfidence: 78.5,
  regimeHistory: [
    { regime: 'RANGE_BOUND', timestamp: Date.now() - 86400000 * 5, confidence: 65 },
    { regime: 'BULL_TRENDING', timestamp: Date.now() - 86400000 * 2, confidence: 72 },
    { regime: 'BULL_TRENDING', timestamp: Date.now(), confidence: 78.5 },
  ],

  // ── Volatility ───────────────────────────────────────────────────────
  indiaVix: 14.2,
  indiaVixChange: -0.85,
  indiaVixChangePercent: -5.65,
  usVix: 16.8,
  usVixChange: 0.42,
  usVixChangePercent: 2.56,

  // ── Market Status ────────────────────────────────────────────────────
  marketStatus: {
    india: {
      status: 'OPEN',
      session: 'NORMAL',
      openTime: '09:15',
      closeTime: '15:30',
      preMarketOpen: '09:00',
      preMarketClose: '09:08',
      nextEvent: 'Market Close',
      nextEventTime: '15:30',
      timezone: 'Asia/Kolkata',
    },
    us: {
      status: 'CLOSED',
      session: 'PRE_MARKET',
      openTime: '09:30',
      closeTime: '16:00',
      preMarketOpen: '04:00',
      preMarketClose: '09:30',
      nextEvent: 'Market Open',
      nextEventTime: '09:30',
      timezone: 'America/New_York',
    },
    crypto: {
      status: 'OPEN',
      session: '24/7',
      nextEvent: null,
      nextEventTime: null,
    },
  },

  // ── Sector Performance ──────────────────────────────────────────────
  sectorPerformance: {
    'IT': { change: 1.42, value: 38245.60 },
    'Banking': { change: -0.23, value: 53472.85 },
    'Pharma': { change: -0.68, value: 19842.30 },
    'Auto': { change: 0.95, value: 22156.40 },
    'Metal': { change: 1.87, value: 8924.50 },
    'Energy': { change: 0.34, value: 12478.90 },
    'FMCG': { change: -0.12, value: 56234.70 },
    'Realty': { change: 2.14, value: 945.80 },
  },

  // ── Actions ──────────────────────────────────────────────────────────
  updatePrice: (symbol, priceData) =>
    set((state) => ({
      prices: {
        ...state.prices,
        [symbol]: {
          ...state.prices[symbol],
          ...priceData,
          timestamp: Date.now(),
        },
      },
    })),

  updatePrices: (priceUpdates) =>
    set((state) => {
      const newPrices = { ...state.prices };
      for (const [symbol, data] of Object.entries(priceUpdates)) {
        newPrices[symbol] = {
          ...newPrices[symbol],
          ...data,
          timestamp: Date.now(),
        };
      }
      return { prices: newPrices };
    }),

  updateIndex: (indexKey, indexData) =>
    set((state) => ({
      indices: {
        ...state.indices,
        [indexKey]: {
          ...state.indices[indexKey],
          ...indexData,
          timestamp: Date.now(),
        },
      },
    })),

  setRegime: (regime, confidence = null) =>
    set((state) => ({
      marketRegime: regime,
      regimeConfidence: confidence ?? state.regimeConfidence,
      regimeHistory: [
        ...state.regimeHistory,
        { regime, timestamp: Date.now(), confidence: confidence ?? state.regimeConfidence },
      ].slice(-20),
    })),

  setVix: (market, value) =>
    set((state) => {
      if (market === 'india') {
        const change = value - (state.indiaVix || 0);
        const changePercent = state.indiaVix ? (change / state.indiaVix) * 100 : 0;
        return { indiaVix: value, indiaVixChange: change, indiaVixChangePercent: changePercent };
      }
      if (market === 'us') {
        const change = value - (state.usVix || 0);
        const changePercent = state.usVix ? (change / state.usVix) * 100 : 0;
        return { usVix: value, usVixChange: change, usVixChangePercent: changePercent };
      }
      return {};
    }),

  setMarketStatus: (market, statusData) =>
    set((state) => ({
      marketStatus: {
        ...state.marketStatus,
        [market]: {
          ...state.marketStatus[market],
          ...statusData,
        },
      },
    })),

  setSectorPerformance: (sectorData) =>
    set(() => ({
      sectorPerformance: sectorData,
    })),

  // ── Computed Getters ─────────────────────────────────────────────────
  getPrice: (symbol) => get().prices[symbol] || null,
  getIndex: (indexKey) => get().indices[indexKey] || null,
  isMarketOpen: (market = 'india') => get().marketStatus[market]?.status === 'OPEN',
}));

export default useMarketStore;
