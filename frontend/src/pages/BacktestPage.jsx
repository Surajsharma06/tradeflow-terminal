import { useEffect, useState } from 'react';
import {
  FlaskConical,
  Cpu,
  Database,
  BarChart3,
  Zap,
  Shield,
} from 'lucide-react';

import BacktestRunner from '../components/tools/BacktestRunner';

// ═══════════════════════════════════════════════════════
// Backtest Page — Strategy Backtesting Engine
// ═══════════════════════════════════════════════════════

export default function BacktestPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  const stagger = (index) => ({
    opacity: mounted ? 1 : 0,
    transform: mounted ? 'translateY(0px)' : 'translateY(20px)',
    transition: `all 0.5s cubic-bezier(0.16, 1, 0.3, 1) ${index * 0.1}s`,
  });

  const capabilities = [
    {
      icon: Cpu,
      title: 'Multi-Strategy Engine',
      desc: 'Test Momentum, Mean Reversion, VWAP Bounce, Trend Following, ORB & more',
    },
    {
      icon: Database,
      title: 'Tick-Level Data',
      desc: '1m to Daily candles with realistic slippage, commission & impact modeling',
    },
    {
      icon: BarChart3,
      title: 'Comprehensive Metrics',
      desc: 'CAGR, Sharpe, Sortino, Calmar, Profit Factor, Max Drawdown & more',
    },
    {
      icon: Shield,
      title: 'Walk-Forward Analysis',
      desc: 'Out-of-sample validation with Monte Carlo simulation for robustness',
    },
  ];

  return (
    <div className="p-4 lg:p-6 min-h-screen">
      {/* ── Header ── */}
      <div style={stagger(0)} className="mb-6">
        <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
          <FlaskConical className="w-6 h-6 text-accent" />
          Strategy Backtester
        </h1>
        <p className="text-xs text-text-tertiary mt-0.5">
          Test strategies against historical data with realistic slippage and
          commission modeling
        </p>
      </div>

      {/* ── Engine Capabilities Banner ── */}
      <div style={stagger(1)} className="mb-6">
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-4 h-4 text-gold" />
            <h2 className="text-sm font-semibold text-text-primary">
              Backtesting Engine Capabilities
            </h2>
          </div>
          <p className="text-xs text-text-secondary leading-relaxed mb-4">
            Our institutional-grade backtesting engine processes tick-level
            historical data across NSE, BSE, and crypto markets. It supports
            multi-timeframe analysis with configurable slippage models,
            brokerage commissions (Zerodha, Upstox, Angel One), STT/CTT
            calculations, and realistic fill simulation. Run walk-forward
            optimization to prevent overfitting and validate strategy robustness
            across different market regimes.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {capabilities.map((cap) => (
              <div
                key={cap.title}
                className="flex items-start gap-3 p-3 rounded-lg bg-surface/50 border border-border/30 hover:border-border-light transition-colors"
              >
                <div className="w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center shrink-0">
                  <cap.icon className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-text-primary mb-0.5">
                    {cap.title}
                  </div>
                  <div className="text-[10px] text-text-tertiary leading-relaxed">
                    {cap.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Backtest Runner (Full Page Component) ── */}
      <div style={stagger(2)}>
        <BacktestRunner />
      </div>
    </div>
  );
}
