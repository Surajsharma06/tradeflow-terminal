import { create } from 'zustand';

const useSignalStore = create((set, get) => ({
  // ── Active Signals ───────────────────────────────────────────────────
  activeSignals: [
    {
      id: 'sig-001',
      symbol: 'SBIN',
      exchange: 'NSE',
      direction: 'LONG',
      strategy: 'Momentum Breakout',
      score: 92,
      confidence: 'HIGH',
      entry: 824.00,
      stopLoss: 805.00,
      target1: 845.00,
      target2: 862.00,
      target3: 880.00,
      riskReward: 2.47,
      currentPrice: 824.55,
      triggerPrice: 826.00,
      status: 'ACTIVE',
      timeframe: '1H',
      timestamp: new Date(Date.now() - 1800000).toISOString(),
      expiresAt: new Date(Date.now() + 14400000).toISOString(),
      notes: 'Strong volume breakout above 820 resistance. RSI at 62, MACD bullish crossover. Sector rotation into PSU banks.',
      indicators: {
        rsi: 62.4,
        macd: 'BULLISH_CROSSOVER',
        ema20: 812.30,
        ema50: 798.45,
        volume: '2.3x avg',
        atr: 18.50,
      },
      sector: 'Banking',
    },
    {
      id: 'sig-002',
      symbol: 'BHARTIARTL',
      exchange: 'NSE',
      direction: 'LONG',
      strategy: 'Trend Continuation',
      score: 88,
      confidence: 'HIGH',
      entry: 1618.00,
      stopLoss: 1585.00,
      target1: 1650.00,
      target2: 1680.00,
      target3: 1720.00,
      riskReward: 2.12,
      currentPrice: 1624.30,
      triggerPrice: null,
      status: 'TRIGGERED',
      timeframe: '4H',
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      expiresAt: new Date(Date.now() + 28800000).toISOString(),
      notes: 'Pullback to 20 EMA in strong uptrend. Telecom sector showing strength. 5G expansion catalyst.',
      indicators: {
        rsi: 58.7,
        macd: 'BULLISH',
        ema20: 1605.40,
        ema50: 1572.80,
        volume: '1.8x avg',
        atr: 32.40,
      },
      sector: 'Telecom',
    },
    {
      id: 'sig-003',
      symbol: 'TATAMOTORS',
      exchange: 'NSE',
      direction: 'SHORT',
      strategy: 'Mean Reversion',
      score: 85,
      confidence: 'HIGH',
      entry: 975.00,
      stopLoss: 998.00,
      target1: 955.00,
      target2: 938.00,
      target3: 920.00,
      riskReward: 2.39,
      currentPrice: 972.40,
      triggerPrice: 970.00,
      status: 'ACTIVE',
      timeframe: '1H',
      timestamp: new Date(Date.now() - 5400000).toISOString(),
      expiresAt: new Date(Date.now() + 10800000).toISOString(),
      notes: 'Overbought RSI with bearish divergence on daily. Auto sector facing headwinds from rising input costs.',
      indicators: {
        rsi: 74.2,
        macd: 'BEARISH_DIVERGENCE',
        ema20: 965.80,
        ema50: 948.30,
        volume: '1.2x avg',
        atr: 24.60,
      },
      sector: 'Auto',
    },
    {
      id: 'sig-004',
      symbol: 'ADANIENT',
      exchange: 'NSE',
      direction: 'LONG',
      strategy: 'Breakout Pullback',
      score: 82,
      confidence: 'MEDIUM',
      entry: 3100.00,
      stopLoss: 3040.00,
      target1: 3160.00,
      target2: 3220.00,
      target3: 3300.00,
      riskReward: 2.0,
      currentPrice: 3124.85,
      triggerPrice: null,
      status: 'TRIGGERED',
      timeframe: '1D',
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      expiresAt: new Date(Date.now() + 43200000).toISOString(),
      notes: 'Breakout above 3080 consolidation zone with high volume. Infrastructure push by government as catalyst.',
      indicators: {
        rsi: 64.8,
        macd: 'BULLISH',
        ema20: 3048.50,
        ema50: 2985.20,
        volume: '2.8x avg',
        atr: 68.30,
      },
      sector: 'Conglomerate',
    },
    {
      id: 'sig-005',
      symbol: 'SUNPHARMA',
      exchange: 'NSE',
      direction: 'SHORT',
      strategy: 'Breakdown',
      score: 78,
      confidence: 'MEDIUM',
      entry: 1548.00,
      stopLoss: 1575.00,
      target1: 1520.00,
      target2: 1495.00,
      target3: 1465.00,
      riskReward: 2.07,
      currentPrice: 1542.35,
      triggerPrice: 1540.00,
      status: 'ACTIVE',
      timeframe: '4H',
      timestamp: new Date(Date.now() - 9000000).toISOString(),
      expiresAt: new Date(Date.now() + 21600000).toISOString(),
      notes: 'Breaking below ascending trendline support. Pharma sector weak on USFDA concerns. Volume increasing on down moves.',
      indicators: {
        rsi: 38.9,
        macd: 'BEARISH_CROSSOVER',
        ema20: 1558.70,
        ema50: 1574.20,
        volume: '1.6x avg',
        atr: 28.90,
      },
      sector: 'Pharma',
    },
    {
      id: 'sig-006',
      symbol: 'LT',
      exchange: 'NSE',
      direction: 'LONG',
      strategy: 'Support Bounce',
      score: 73,
      confidence: 'MEDIUM',
      entry: 3530.00,
      stopLoss: 3480.00,
      target1: 3580.00,
      target2: 3630.00,
      target3: 3700.00,
      riskReward: 2.0,
      currentPrice: 3542.10,
      triggerPrice: null,
      status: 'TRIGGERED',
      timeframe: '1H',
      timestamp: new Date(Date.now() - 10800000).toISOString(),
      expiresAt: new Date(Date.now() + 18000000).toISOString(),
      notes: 'Bouncing off strong demand zone at 3500. Infra capex cycle supportive. Order book at record highs.',
      indicators: {
        rsi: 52.3,
        macd: 'NEUTRAL',
        ema20: 3528.40,
        ema50: 3510.60,
        volume: '1.1x avg',
        atr: 52.80,
      },
      sector: 'Infrastructure',
    },
  ],

  // ── Signal History ───────────────────────────────────────────────────
  signalHistory: [
    { id: 'hist-001', symbol: 'WIPRO', direction: 'LONG', score: 81, result: 'TARGET_1_HIT', pnl: 4250, timestamp: new Date(Date.now() - 86400000).toISOString() },
    { id: 'hist-002', symbol: 'ICICIBANK', direction: 'SHORT', score: 76, result: 'STOP_LOSS_HIT', pnl: -3120, timestamp: new Date(Date.now() - 86400000).toISOString() },
    { id: 'hist-003', symbol: 'MARUTI', direction: 'LONG', score: 89, result: 'TARGET_2_HIT', pnl: 8940, timestamp: new Date(Date.now() - 86400000 * 2).toISOString() },
    { id: 'hist-004', symbol: 'HDFCBANK', direction: 'LONG', score: 85, result: 'TARGET_1_HIT', pnl: 5670, timestamp: new Date(Date.now() - 86400000 * 2).toISOString() },
    { id: 'hist-005', symbol: 'TCS', direction: 'SHORT', score: 77, result: 'TARGET_3_HIT', pnl: 12350, timestamp: new Date(Date.now() - 86400000 * 3).toISOString() },
    { id: 'hist-006', symbol: 'RELIANCE', direction: 'LONG', score: 91, result: 'TARGET_2_HIT', pnl: 9820, timestamp: new Date(Date.now() - 86400000 * 3).toISOString() },
    { id: 'hist-007', symbol: 'AXISBANK', direction: 'LONG', score: 72, result: 'EXPIRED', pnl: -1240, timestamp: new Date(Date.now() - 86400000 * 4).toISOString() },
    { id: 'hist-008', symbol: 'INFY', direction: 'SHORT', score: 83, result: 'TARGET_1_HIT', pnl: 6430, timestamp: new Date(Date.now() - 86400000 * 4).toISOString() },
  ],

  // ── Stats ────────────────────────────────────────────────────────────
  totalSignalsToday: 9,
  signalsTriggered: 3,
  signalsPending: 3,
  signalsExpired: 2,
  signalHitRate: 67.8,
  avgSignalScore: 83.0,

  // ── Filters ──────────────────────────────────────────────────────────
  filters: {
    minScore: 70,
    direction: 'ALL', // 'ALL' | 'LONG' | 'SHORT'
    timeframe: 'ALL',
    confidence: 'ALL', // 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'
    sector: 'ALL',
  },

  // ── Actions ──────────────────────────────────────────────────────────
  addSignal: (signal) =>
    set((state) => ({
      activeSignals: [
        {
          ...signal,
          id: `sig-${String(Date.now()).slice(-6)}`,
          timestamp: new Date().toISOString(),
          status: signal.status || 'ACTIVE',
        },
        ...state.activeSignals,
      ],
      totalSignalsToday: state.totalSignalsToday + 1,
    })),

  updateSignal: (signalId, updates) =>
    set((state) => ({
      activeSignals: state.activeSignals.map((s) =>
        s.id === signalId ? { ...s, ...updates } : s
      ),
    })),

  removeSignal: (signalId) =>
    set((state) => {
      const signal = state.activeSignals.find((s) => s.id === signalId);
      return {
        activeSignals: state.activeSignals.filter((s) => s.id !== signalId),
        signalHistory: signal
          ? [{ ...signal, removedAt: new Date().toISOString() }, ...state.signalHistory]
          : state.signalHistory,
      };
    }),

  clearSignals: () =>
    set((state) => ({
      activeSignals: [],
      signalHistory: [...state.activeSignals, ...state.signalHistory],
    })),

  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
    })),

  // ── Computed ─────────────────────────────────────────────────────────
  getFilteredSignals: () => {
    const state = get();
    const { filters, activeSignals } = state;

    return activeSignals.filter((signal) => {
      if (signal.score < filters.minScore) return false;
      if (filters.direction !== 'ALL' && signal.direction !== filters.direction) return false;
      if (filters.timeframe !== 'ALL' && signal.timeframe !== filters.timeframe) return false;
      if (filters.confidence !== 'ALL' && signal.confidence !== filters.confidence) return false;
      if (filters.sector !== 'ALL' && signal.sector !== filters.sector) return false;
      return true;
    });
  },

  getSignalsByDirection: (direction) =>
    get().activeSignals.filter((s) => s.direction === direction),

  getHighConfidenceSignals: () =>
    get().activeSignals.filter((s) => s.score >= 85),

  getSignalById: (id) =>
    get().activeSignals.find((s) => s.id === id),
}));

export default useSignalStore;
