import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Shield, Zap, RefreshCw, AlertTriangle, TrendingUp, TrendingDown,
  ChevronDown, ChevronUp, FlaskConical, Scale, BookOpen,
} from 'lucide-react';
import { API } from '../lib/api';

// ─────────────────────────────────────────────────────────────────────────────
// Demo fallback (shown when backend is unreachable) — clearly labelled.
// ─────────────────────────────────────────────────────────────────────────────
const DEMO_SIGNALS = [
  {
    pair: 'EUR/USD', direction: 'BUY', entry: 1.13520, stop_loss: 1.13140,
    take_profit: 1.14090, risk_reward: 1.5, rsi: 44.2, atr: 0.00253,
    strategy: 'EMA trend + RSI pullback + ATR stops', timeframe: '1H',
    reasons: [
      'Uptrend filter: EMA20 (1.13310) above EMA50 (1.12980)',
      'Price 1.13520 trading above EMA20',
      'RSI(14) pullback: dipped below 40 within last 5 bars (min 36.8), now recovered to 44.2',
      'Volatility stop: 1.5×ATR(14) = 0.00380',
    ],
    position: { units: 26315.79, risk_amount: 100, risk_pct: 1.0, stop_distance_pips: 38 },
  },
];

const fadeUp = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
};

// ─────────────────────────────────────────────────────────────────────────────
// Signal card — shows WHY the signal fired, not just buy/sell
// ─────────────────────────────────────────────────────────────────────────────
function SignalCard({ sig, idx }) {
  const [expanded, setExpanded] = useState(idx === 0);
  const isBuy = sig.direction === 'BUY';

  return (
    <motion.div
      {...fadeUp}
      transition={{ delay: idx * 0.06, duration: 0.25 }}
      className="glass-card overflow-hidden"
    >
      {/* Header row */}
      <div className="flex items-center gap-3 p-4">
        <span className={`flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1.5 rounded-lg flex-shrink-0
          ${isBuy ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}`}>
          {isBuy ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          {sig.direction}
        </span>
        <div className="flex-1 min-w-0">
          <div className="font-mono text-base font-bold text-text-primary">{sig.pair}</div>
          <div className="text-[10px] text-text-tertiary truncate">{sig.strategy} · {sig.timeframe}</div>
        </div>
        <div className="hidden sm:flex items-center gap-4 flex-shrink-0">
          <div className="text-right">
            <div className="text-[9px] text-text-muted uppercase tracking-wider">Entry</div>
            <div className="font-mono text-xs text-text-primary">{sig.entry}</div>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-negative uppercase tracking-wider">Stop</div>
            <div className="font-mono text-xs text-negative">{sig.stop_loss}</div>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-positive uppercase tracking-wider">Target</div>
            <div className="font-mono text-xs text-positive">{sig.take_profit}</div>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-text-muted uppercase tracking-wider">R:R</div>
            <div className="font-mono text-xs font-bold text-accent">1:{sig.risk_reward}</div>
          </div>
        </div>
        <button
          onClick={() => setExpanded((e) => !e)}
          className="p-2 rounded-md hover:bg-surface-hover text-text-secondary cursor-pointer"
          aria-expanded={expanded}
          aria-label={expanded ? 'Hide signal reasoning' : 'Show signal reasoning'}
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Why this fired */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Mobile: entry/sl/tp */}
          <div className="sm:hidden grid grid-cols-4 gap-2 text-center">
            {[['Entry', sig.entry, 'text-text-primary'], ['Stop', sig.stop_loss, 'text-negative'],
              ['Target', sig.take_profit, 'text-positive'], ['R:R', `1:${sig.risk_reward}`, 'text-accent']].map(([l, v, c]) => (
              <div key={l} className="bg-surface/50 rounded-lg py-1.5">
                <div className="text-[9px] text-text-muted uppercase">{l}</div>
                <div className={`font-mono text-[11px] font-semibold ${c}`}>{v}</div>
              </div>
            ))}
          </div>

          <div className="rounded-lg bg-surface/60 border border-border/40 p-3">
            <div className="flex items-center gap-1.5 mb-2">
              <BookOpen size={12} className="text-accent" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">
                Why this signal fired
              </span>
            </div>
            <ul className="space-y-1.5">
              {sig.reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[11px] text-text-secondary leading-relaxed">
                  <span className="w-1 h-1 rounded-full bg-accent mt-1.5 flex-shrink-0" />
                  {r}
                </li>
              ))}
            </ul>
          </div>

          {/* Position sizing */}
          {sig.position && (
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg bg-accent-subtle/40 border border-accent/20 px-3 py-2">
              <div className="flex items-center gap-1.5">
                <Scale size={12} className="text-accent" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-accent">Suggested size</span>
              </div>
              <span className="font-mono text-[11px] text-text-primary">{Number(sig.position.units).toLocaleString()} units</span>
              <span className="font-mono text-[11px] text-text-secondary">risking ${sig.position.risk_amount} ({sig.position.risk_pct}%)</span>
              <span className="font-mono text-[11px] text-text-secondary">{sig.position.stop_distance_pips} pip stop</span>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Backtest panel
// ─────────────────────────────────────────────────────────────────────────────
function BacktestPanel() {
  const [pair, setPair] = useState('EURUSD');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const run = async () => {
    setRunning(true); setError(null);
    try {
      const res = await fetch(`${API}/api/v1/lipschutz/backtest?pair=${pair}&days=180`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(`Backtest unavailable (${e.message}) — start the backend for live results.`);
    } finally {
      setRunning(false);
    }
  };

  const stats = result && [
    ['Trades', result.total_trades, 'text-text-primary'],
    ['Win rate', `${result.win_rate_pct}%`, result.win_rate_pct >= 50 ? 'text-positive' : 'text-warning'],
    ['Avg R', result.avg_r_multiple, result.avg_r_multiple > 0 ? 'text-positive' : 'text-negative'],
    ['Profit factor', result.profit_factor ?? '—', 'text-text-primary'],
    ['Return', `${result.return_pct}%`, result.return_pct >= 0 ? 'text-positive' : 'text-negative'],
    ['Max DD', `-${result.max_drawdown_pct}%`, 'text-negative'],
  ];

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FlaskConical size={14} className="text-purple" />
        <span className="text-sm font-semibold text-text-primary">Verify the rules yourself</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">180-day walk-forward</span>
      </div>
      <p className="text-[11px] text-text-secondary leading-relaxed">
        Don't trust it — test it. This replays the exact same rules bar-by-bar over real
        historical data. Stats include losses and drawdowns, not cherry-picked wins.
      </p>
      <div className="flex items-center gap-2">
        <select
          value={pair}
          onChange={(e) => setPair(e.target.value)}
          className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-text-primary cursor-pointer"
          aria-label="Backtest pair"
        >
          {['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD'].map((p) => (
            <option key={p} value={p}>{p.slice(0, 3)}/{p.slice(3)}</option>
          ))}
        </select>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={run}
          disabled={running}
          className="flex items-center gap-1.5 btn-gradient disabled:opacity-50 text-white text-xs font-semibold px-4 py-1.5 rounded-lg cursor-pointer"
        >
          <RefreshCw size={12} className={running ? 'animate-spin' : ''} />
          {running ? 'Running…' : 'Run backtest'}
        </motion.button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-[11px] text-warning bg-warning-subtle rounded-lg px-3 py-2">
          <AlertTriangle size={12} className="flex-shrink-0" /> {error}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {stats.map(([label, value, cls]) => (
              <div key={label} className="bg-surface/60 rounded-lg p-2 text-center">
                <div className="text-[9px] text-text-muted uppercase tracking-wider">{label}</div>
                <div className={`font-mono text-sm font-bold ${cls}`}>{value}</div>
              </div>
            ))}
          </div>
          {/* Equity curve sparkline */}
          {result.equity_curve?.length > 1 && (
            <svg viewBox="0 0 400 60" className="w-full h-14" preserveAspectRatio="none" aria-label="Equity curve">
              <polyline
                points={result.equity_curve.map((v, i) => {
                  const min = Math.min(...result.equity_curve);
                  const max = Math.max(...result.equity_curve);
                  const x = (i / (result.equity_curve.length - 1)) * 400;
                  const y = 55 - ((v - min) / (max - min || 1)) * 50;
                  return `${x},${y}`;
                }).join(' ')}
                fill="none"
                stroke={result.return_pct >= 0 ? '#3fb950' : '#f85149'}
                strokeWidth="1.5"
              />
            </svg>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function LipschutzPage() {
  const [signals, setSignals] = useState(null);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [breaker, setBreaker] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/lipschutz/signals`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSignals(data.signals ?? []);
      setBreaker(data.circuit_breaker ? data.circuit_breaker_reason : null);
      setDemo(false);
    } catch {
      setSignals(DEMO_SIGNALS);
      setDemo(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-4 lg:p-5 min-h-screen space-y-4 max-w-[1100px] mx-auto">

      {/* Header */}
      <motion.div {...fadeUp} transition={{ duration: 0.25 }} className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gold-subtle flex items-center justify-center">
              <Shield size={16} className="text-gold" />
            </div>
            <h1 className="text-xl font-bold text-text-primary">Discipline Mode</h1>
            {demo && (
              <span className="px-2 py-0.5 rounded-full bg-warning-subtle text-warning text-[9px] font-bold">DEMO DATA</span>
            )}
          </div>
          <p className="text-xs text-text-secondary mt-1 max-w-[560px] leading-relaxed">
            Rules-based signals in the spirit of Bill Lipschutz: risk management first,
            prediction second. Every signal shows exactly why it fired — no black box.
          </p>
        </div>
        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={load}
          className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary bg-surface border border-border rounded-lg px-3 py-2 transition-colors cursor-pointer"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
        </motion.button>
      </motion.div>

      {/* Risk rules banner */}
      <motion.div {...fadeUp} transition={{ delay: 0.05, duration: 0.25 }}
        className="glass-card p-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        {[
          ['Max risk per trade', '1% of equity'],
          ['Stop-loss', 'Mandatory · 1.5×ATR'],
          ['Take-profit', 'Fixed 1.5R'],
          ['Circuit breaker', '-3% day / -6% week'],
        ].map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <Shield size={11} className="text-gold flex-shrink-0" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider">{k}</span>
            <span className="text-[11px] font-semibold text-text-primary">{v}</span>
          </div>
        ))}
      </motion.div>

      {/* Circuit breaker warning */}
      {breaker && (
        <div className="flex items-center gap-2 text-xs text-negative bg-negative-subtle border border-negative/30 rounded-lg px-4 py-3">
          <AlertTriangle size={14} className="flex-shrink-0" />
          <span><strong>Circuit breaker active:</strong> {breaker}</span>
        </div>
      )}

      {/* Signals */}
      <div className="space-y-3">
        {loading ? (
          <div className="glass-card p-8 flex items-center justify-center gap-2 text-text-tertiary text-sm">
            <RefreshCw size={14} className="animate-spin" /> Scanning pairs against the rule set…
          </div>
        ) : signals?.length === 0 && !breaker ? (
          <div className="glass-card p-8 text-center space-y-1">
            <Zap size={18} className="mx-auto text-text-tertiary" />
            <div className="text-sm font-semibold text-text-primary">No setups right now</div>
            <div className="text-[11px] text-text-secondary">
              The rules are strict by design — discipline means waiting. Check back later.
            </div>
          </div>
        ) : (
          signals?.map((sig, i) => <SignalCard key={`${sig.pair}-${i}`} sig={sig} idx={i} />)
        )}
      </div>

      {/* Backtest */}
      <BacktestPanel />

      {/* Honest disclaimer */}
      <div className="flex items-start gap-2 rounded-lg border border-border/60 bg-surface/40 px-4 py-3">
        <AlertTriangle size={13} className="text-warning flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-text-secondary leading-relaxed">
          <strong className="text-text-primary">This is a decision-support tool, not a guarantee.</strong>{' '}
          No strategy wins consistently in all markets, and historical stats do not predict
          future results. Forex trading carries a real risk of losing money — never risk
          capital you cannot afford to lose, and never exceed the position size the risk
          engine suggests.
        </p>
      </div>
    </div>
  );
}
