import { create } from 'zustand';

const usePortfolioStore = create((set, get) => ({
  // ── Positions ────────────────────────────────────────────────────────
  positions: [
    {
      id: 'pos-001',
      symbol: 'RELIANCE',
      exchange: 'NSE',
      direction: 'LONG',
      quantity: 50,
      entryPrice: 2847.00,
      currentPrice: 2892.45,
      stopLoss: 2780.00,
      target: 2980.00,
      entryTime: new Date(Date.now() - 86400000 * 3).toISOString(),
      strategy: 'Momentum Breakout',
      pnl: (2892.45 - 2847.00) * 50,
      pnlPercent: ((2892.45 - 2847.00) / 2847.00) * 100,
      riskReward: ((2980.00 - 2847.00) / (2847.00 - 2780.00)).toFixed(2),
      charges: 142.35,
      status: 'ACTIVE',
      sector: 'Energy',
      trailingStop: 2860.00,
      daysHeld: 3,
      capitalUsed: 2847.00 * 50,
    },
    {
      id: 'pos-002',
      symbol: 'TCS',
      exchange: 'NSE',
      direction: 'SHORT',
      quantity: 25,
      entryPrice: 4210.00,
      currentPrice: 4185.30,
      stopLoss: 4290.00,
      target: 4080.00,
      entryTime: new Date(Date.now() - 86400000 * 1).toISOString(),
      strategy: 'Mean Reversion',
      pnl: (4210.00 - 4185.30) * 25,
      pnlPercent: ((4210.00 - 4185.30) / 4210.00) * 100,
      riskReward: ((4210.00 - 4080.00) / (4290.00 - 4210.00)).toFixed(2),
      charges: 105.25,
      status: 'ACTIVE',
      sector: 'IT',
      trailingStop: null,
      daysHeld: 1,
      capitalUsed: 4210.00 * 25,
    },
    {
      id: 'pos-003',
      symbol: 'HDFCBANK',
      exchange: 'NSE',
      direction: 'LONG',
      quantity: 75,
      entryPrice: 1823.00,
      currentPrice: 1847.65,
      stopLoss: 1785.00,
      target: 1920.00,
      entryTime: new Date(Date.now() - 86400000 * 5).toISOString(),
      strategy: 'Support Bounce',
      pnl: (1847.65 - 1823.00) * 75,
      pnlPercent: ((1847.65 - 1823.00) / 1823.00) * 100,
      riskReward: ((1920.00 - 1823.00) / (1823.00 - 1785.00)).toFixed(2),
      charges: 136.73,
      status: 'ACTIVE',
      sector: 'Banking',
      trailingStop: 1835.00,
      daysHeld: 5,
      capitalUsed: 1823.00 * 75,
    },
    {
      id: 'pos-004',
      symbol: 'INFY',
      exchange: 'NSE',
      direction: 'LONG',
      quantity: 60,
      entryPrice: 1890.00,
      currentPrice: 1912.80,
      stopLoss: 1845.00,
      target: 1985.00,
      entryTime: new Date(Date.now() - 86400000 * 2).toISOString(),
      strategy: 'Breakout Pullback',
      pnl: (1912.80 - 1890.00) * 60,
      pnlPercent: ((1912.80 - 1890.00) / 1890.00) * 100,
      riskReward: ((1985.00 - 1890.00) / (1890.00 - 1845.00)).toFixed(2),
      charges: 113.40,
      status: 'ACTIVE',
      sector: 'IT',
      trailingStop: 1900.00,
      daysHeld: 2,
      capitalUsed: 1890.00 * 60,
    },
  ],

  // ── Capital ──────────────────────────────────────────────────────────
  totalCapital: 1000000,
  usedCapital: 2847.00 * 50 + 4210.00 * 25 + 1823.00 * 75 + 1890.00 * 60,
  availableCapital: 0, // calculated below

  // ── PnL ──────────────────────────────────────────────────────────────
  dailyPnl: 12847.50,
  dailyPnlPercent: 1.28,
  weeklyPnl: 34562.80,
  weeklyPnlPercent: 3.46,
  monthlyPnl: 78945.30,
  monthlyPnlPercent: 7.89,
  totalPnl: 156230.75,
  totalPnlPercent: 15.62,

  // ── Risk Metrics ─────────────────────────────────────────────────────
  drawdown: 2.3,
  maxDrawdown: 5.8,
  currentRisk: 3.2,
  maxRiskPerTrade: 2.0,
  maxPositions: 8,
  sharpeRatio: 1.84,
  sortinoRatio: 2.12,
  calmarRatio: 2.69,
  winRate: 64.7,
  avgWin: 18450,
  avgLoss: -9870,
  profitFactor: 1.87,

  // ── Trade History Summary ────────────────────────────────────────────
  totalTrades: 127,
  winningTrades: 82,
  losingTrades: 45,
  avgHoldingPeriod: 3.2,

  // ── Equity Curve Data ────────────────────────────────────────────────
  equityCurve: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - 86400000 * (29 - i)).toISOString().split('T')[0],
    equity: 1000000 + Math.round((Math.random() * 20000 - 5000) * (i + 1) / 10),
    drawdown: -(Math.random() * 4).toFixed(2),
  })),

  // ── Actions ──────────────────────────────────────────────────────────
  addPosition: (position) =>
    set((state) => {
      const newPosition = {
        ...position,
        id: `pos-${String(state.positions.length + 1).padStart(3, '0')}`,
        entryTime: new Date().toISOString(),
        status: 'ACTIVE',
        pnl: 0,
        pnlPercent: 0,
        daysHeld: 0,
        capitalUsed: position.entryPrice * position.quantity,
      };
      const newUsedCapital = state.usedCapital + newPosition.capitalUsed;
      return {
        positions: [...state.positions, newPosition],
        usedCapital: newUsedCapital,
        availableCapital: state.totalCapital - newUsedCapital,
      };
    }),

  removePosition: (positionId) =>
    set((state) => {
      const position = state.positions.find((p) => p.id === positionId);
      if (!position) return {};
      const newUsedCapital = state.usedCapital - position.capitalUsed;
      return {
        positions: state.positions.filter((p) => p.id !== positionId),
        usedCapital: newUsedCapital,
        availableCapital: state.totalCapital - newUsedCapital,
      };
    }),

  updatePosition: (positionId, updates) =>
    set((state) => ({
      positions: state.positions.map((p) => {
        if (p.id !== positionId) return p;
        const updated = { ...p, ...updates };
        // Recalculate PnL
        if (updated.currentPrice) {
          if (updated.direction === 'LONG') {
            updated.pnl = (updated.currentPrice - updated.entryPrice) * updated.quantity;
            updated.pnlPercent = ((updated.currentPrice - updated.entryPrice) / updated.entryPrice) * 100;
          } else {
            updated.pnl = (updated.entryPrice - updated.currentPrice) * updated.quantity;
            updated.pnlPercent = ((updated.entryPrice - updated.currentPrice) / updated.entryPrice) * 100;
          }
        }
        return updated;
      }),
    })),

  updatePnl: (pnlData) =>
    set(() => ({
      ...pnlData,
    })),

  updateCapital: (totalCapital) =>
    set((state) => ({
      totalCapital,
      availableCapital: totalCapital - state.usedCapital,
    })),

  // ── Computed ─────────────────────────────────────────────────────────
  getActivePositions: () => get().positions.filter((p) => p.status === 'ACTIVE'),
  getPositionBySymbol: (symbol) => get().positions.find((p) => p.symbol === symbol),
  getTotalUnrealizedPnl: () => get().positions.reduce((sum, p) => sum + (p.pnl || 0), 0),
  getCapitalUtilization: () => {
    const state = get();
    return ((state.usedCapital / state.totalCapital) * 100).toFixed(1);
  },
}));

// Initialize available capital
const initialState = usePortfolioStore.getState();
usePortfolioStore.setState({
  availableCapital: initialState.totalCapital - initialState.usedCapital,
});

export default usePortfolioStore;
