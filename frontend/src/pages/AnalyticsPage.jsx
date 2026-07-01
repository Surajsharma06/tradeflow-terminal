import { useEffect, useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Zap,
  Target,
  Award,
  Activity,
  BarChart3,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';

import useCurrencyStore, { RATES, SYMBOLS } from '../stores/currencyStore';
import StatCard from '../components/common/StatCard';
import PerformanceChart from '../components/analytics/PerformanceChart';
import PnLCalendar from '../components/analytics/PnLCalendar';
import StrategyBreakdown from '../components/analytics/StrategyBreakdown';
import DrawdownChart from '../components/analytics/DrawdownChart';
import WinLossStreak from '../components/analytics/WinLossStreak';
import { API } from '../lib/api';

// ═══════════════════════════════════════════════════════
// Analytics Page — Performance Deep Dive
// ═══════════════════════════════════════════════════════

export default function AnalyticsPage() {
  const [mounted, setMounted]   = useState(false);
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const { format, currency }   = useCurrencyStore();

  const fetchData = async (forceRefresh = false) => {
    try {
      if (forceRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const url = `${API}/api/v1/analytics/pnl-backtest${forceRefresh ? '?refresh=true' : ''}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    fetchData();
    return () => clearTimeout(t);
  }, []);

  const stagger = (index) => ({
    opacity:   mounted ? 1 : 0,
    transform: mounted ? 'translateY(0px)' : 'translateY(20px)',
    transition: `all 0.5s cubic-bezier(0.16, 1, 0.3, 1) ${index * 0.08}s`,
  });

  const summary     = data?.summary ?? {};
  const totalPnlUsd = summary.total_pnl_usd ?? 0;
  const returnPct   = summary.return_pct ?? 0;
  const winRate     = summary.win_rate ?? 0;
  const pf          = summary.profit_factor ?? 0;
  const sharpe      = summary.sharpe_ratio ?? 0;
  const maxDd       = summary.max_drawdown_pct ?? 0;

  const rate        = RATES[currency]  ?? 1;
  const sym         = SYMBOLS[currency] ?? '$';
  const totalPnlLocal = +(totalPnlUsd * rate).toFixed(2);

  return (
    <div className="p-4 lg:p-6 min-h-screen">
      {/* ── Header ── */}
      <div style={stagger(0)} className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-accent" />
            Performance Analytics
          </h1>
          <p className="text-xs text-text-tertiary mt-0.5">
            Real 6-month SMC walk-forward backtest — 5 forex pairs
            {data?.generated_at && (
              <span className="ml-2 text-text-muted">
                · Last run: {new Date(data.generated_at).toLocaleString()}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-subtle text-accent text-xs font-medium hover:bg-accent/20 transition-colors disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? 'Running backtest…' : 'Refresh'}
        </button>
      </div>

      {/* ── Error state ── */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-negative-subtle border border-negative/30 text-negative text-sm mb-4">
          <AlertCircle size={16} />
          Backtest error: {error}. Showing mock data in charts.
        </div>
      )}

      {/* ── Stat Cards Row ── */}
      <div style={stagger(1)} className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <StatCard
          title={`Total P&L (${currency})`}
          value={totalPnlLocal}
          prefix={sym}
          decimals={0}
          icon={TrendingUp}
          trend={totalPnlUsd >= 0 ? 'up' : 'down'}
          changePercent={returnPct}
        />
        <StatCard
          title="Return %"
          value={returnPct}
          suffix="%"
          decimals={2}
          icon={Zap}
          trend={returnPct >= 0 ? 'up' : 'down'}
        />
        <StatCard
          title="Sharpe Ratio"
          value={sharpe}
          decimals={2}
          icon={Award}
          trend={sharpe >= 1.5 ? 'up' : 'flat'}
        />
        <StatCard
          title="Win Rate"
          value={winRate}
          suffix="%"
          decimals={1}
          icon={Target}
          trend={winRate >= 55 ? 'up' : 'down'}
        />
        <StatCard
          title="Profit Factor"
          value={pf}
          decimals={2}
          icon={Activity}
          trend={pf >= 1.5 ? 'up' : 'flat'}
        />
        <StatCard
          title="Max Drawdown"
          value={maxDd}
          suffix="%"
          prefix="-"
          decimals={1}
          icon={TrendingDown}
          trend="down"
        />
      </div>

      {/* ── Equity Curve (Full Width) ── */}
      <div style={stagger(2)} className="mb-6">
        <PerformanceChart
          equityCurve={data?.equity_curve}
          startingCapital={summary.starting_capital_usd}
          loading={loading}
        />
      </div>

      {/* ── PnL Calendar + Strategy Breakdown ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div style={stagger(3)}>
          <PnLCalendar
            calendarPnl={data?.calendar_pnl}
            monthlyPnl={data?.monthly_pnl}
            loading={loading}
          />
        </div>
        <div style={stagger(4)}>
          <StrategyBreakdown />
        </div>
      </div>

      {/* ── Drawdown + Win/Loss Streak ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div style={stagger(5)}>
          <DrawdownChart equityCurve={data?.equity_curve} loading={loading} />
        </div>
        <div style={stagger(6)}>
          <WinLossStreak trades={data?.recent_trades} loading={loading} />
        </div>
      </div>

      {/* ── Per-Pair Stats Table ── */}
      {data?.pair_stats?.length > 0 && (
        <div style={stagger(7)} className="glass-card p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
            <BarChart3 size={15} className="text-accent" />
            Per-Pair Breakdown — 6 Months
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border/30">
                  {['Pair','Trades','Wins','Win Rate','Pips','P&L','Profit Factor'].map(h => (
                    <th key={h} className="pb-2 pr-4 text-left text-text-tertiary font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.pair_stats.map((p) => (
                  <tr key={p.pair} className="border-b border-border/10 hover:bg-surface-hover/30 transition-colors">
                    <td className="py-2 pr-4 font-semibold text-text-primary">{p.pair}</td>
                    <td className="py-2 pr-4 text-text-secondary">{p.total_trades}</td>
                    <td className="py-2 pr-4 text-text-secondary">{p.wins}</td>
                    <td className={`py-2 pr-4 font-medium ${p.win_rate >= 55 ? 'text-positive' : p.win_rate >= 45 ? 'text-warning' : 'text-negative'}`}>
                      {p.win_rate}%
                    </td>
                    <td className={`py-2 pr-4 font-tabular ${p.total_pips >= 0 ? 'text-positive' : 'text-negative'}`}>
                      {p.total_pips >= 0 ? '+' : ''}{p.total_pips}
                    </td>
                    <td className={`py-2 pr-4 font-tabular font-semibold ${p.pnl_usd >= 0 ? 'text-positive' : 'text-negative'}`}>
                      {format(p.pnl_usd, 2)}
                    </td>
                    <td className={`py-2 pr-4 font-tabular ${p.profit_factor >= 1.5 ? 'text-positive' : p.profit_factor >= 1.0 ? 'text-warning' : 'text-negative'}`}>
                      {p.profit_factor}×
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Recent Trades ── */}
      {data?.recent_trades?.length > 0 && (
        <div style={stagger(8)} className="glass-card p-4 mt-4">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Recent Trades</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border/30">
                  {['Pair','Direction','Entry','Exit','Result','Pips','P&L'].map(h => (
                    <th key={h} className="pb-2 pr-4 text-left text-text-tertiary font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.recent_trades.slice(0, 15).map((t, i) => (
                  <tr key={i} className="border-b border-border/10 hover:bg-surface-hover/30 transition-colors">
                    <td className="py-1.5 pr-4 font-medium text-text-primary">{t.pair}</td>
                    <td className={`py-1.5 pr-4 font-bold text-[10px] ${t.direction === 'BUY' ? 'text-positive' : 'text-negative'}`}>
                      {t.direction}
                    </td>
                    <td className="py-1.5 pr-4 text-text-muted font-tabular text-[10px]">
                      {t.entry_time ? new Date(t.entry_time).toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                    </td>
                    <td className="py-1.5 pr-4 text-text-muted font-tabular text-[10px]">
                      {t.exit_time ? new Date(t.exit_time).toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                    </td>
                    <td className={`py-1.5 pr-4 font-bold text-[10px] ${t.result === 'WIN' ? 'text-positive' : t.result === 'LOSS' ? 'text-negative' : 'text-warning'}`}>
                      {t.result}
                    </td>
                    <td className={`py-1.5 pr-4 font-tabular ${t.pnl_pips >= 0 ? 'text-positive' : 'text-negative'}`}>
                      {t.pnl_pips >= 0 ? '+' : ''}{t.pnl_pips}
                    </td>
                    <td className={`py-1.5 pr-4 font-tabular font-semibold ${t.pnl_usd >= 0 ? 'text-positive' : 'text-negative'}`}>
                      {format(t.pnl_usd, 2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
