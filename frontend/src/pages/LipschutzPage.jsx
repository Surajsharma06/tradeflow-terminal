import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Shield, Zap, RefreshCw, AlertTriangle, TrendingUp, TrendingDown,
  ChevronDown, ChevronUp, FlaskConical, Scale, BookOpen, Users,
  Crown, PauseCircle, Activity,
} from 'lucide-react';
import { API } from '../lib/api';

const fadeUp = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
};

const REGIME_STYLE = {
  TRENDING_UP:   { label: 'Trending ↑', cls: 'bg-positive-subtle text-positive' },
  TRENDING_DOWN: { label: 'Trending ↓', cls: 'bg-negative-subtle text-negative' },
  RANGING:       { label: 'Ranging',    cls: 'bg-info-subtle text-info' },
  CHOPPY:        { label: 'Choppy — sit out', cls: 'bg-warning-subtle text-warning' },
  NO_DATA:       { label: 'No data',    cls: 'bg-surface-hover text-text-tertiary' },
};

// ─────────────────────────────────────────────────────────────────────────────
// Best Trade hero card — the 1-2 setups that clear the quality bar
// ─────────────────────────────────────────────────────────────────────────────
function ScoreRing({ score }) {
  const r = 26;
  const circ = 2 * Math.PI * r;
  const color = score >= 80 ? '#34d764' : score >= 70 ? '#4d9fff' : '#f2c14e';
  return (
    <div className="relative w-[72px] h-[72px] flex-shrink-0" role="img"
         aria-label={`Quality score ${score} out of 100`}>
      <svg viewBox="0 0 64 64" className="w-full h-full -rotate-90">
        <circle cx="32" cy="32" r={r} fill="none" stroke="var(--color-border)" strokeWidth="5" />
        <circle
          cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * circ} ${circ}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-lg font-bold text-text-primary leading-none">{score}</span>
        <span className="text-[8px] text-text-tertiary">/100</span>
      </div>
    </div>
  );
}

function BestTradeCard({ sig, rank }) {
  const [showFactors, setShowFactors] = useState(false);
  const isBuy = sig.direction === 'BUY';
  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: rank * 0.08, duration: 0.3 }}
      className="glass-card-elevated overflow-hidden border-2 !border-gold/40"
    >
      {/* Gold ribbon */}
      <div className="flex items-center gap-2 px-4 py-2 bg-gold-subtle border-b border-gold/20">
        <Crown size={13} className="text-gold" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-gold">
          {rank === 0 ? 'Best trade right now' : 'Runner-up'}
        </span>
        <span className="ml-auto text-[9px] font-bold px-2 py-0.5 rounded-full badge-gradient text-white">
          {sig.quality_grade}
        </span>
      </div>

      <div className="p-4 flex items-center gap-4 flex-wrap">
        <ScoreRing score={sig.quality_score} />
        <div className="flex-1 min-w-[180px]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-lg
              ${isBuy ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}`}>
              {isBuy ? <TrendingUp size={12} /> : <TrendingDown size={12} />} {sig.direction}
            </span>
            <span className="font-mono text-lg font-bold text-text-primary">{sig.pair}</span>
            {sig.conviction === 'HIGH' && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-purple-subtle text-purple">
                ×{sig.confluence} LEGENDS
              </span>
            )}
          </div>
          <div className="text-[11px] text-text-secondary mt-1">
            <span className="text-purple font-semibold">{sig.trader}</span> — {sig.rule}
          </div>
          <div className="flex items-center gap-4 mt-2 font-mono text-[11px] flex-wrap">
            <span className="text-text-secondary">Entry <span className="text-text-primary font-bold">{sig.entry}</span></span>
            <span className="text-negative">SL {sig.stop_loss}</span>
            <span className="text-positive">TP {sig.take_profit}</span>
            <span className="text-accent font-bold">R:R 1:{sig.risk_reward}</span>
            {sig.position && (
              <span className="text-text-tertiary">{sig.risk_pct_used}% risk · {Number(sig.position.units).toLocaleString()} units</span>
            )}
          </div>
        </div>
        <button
          onClick={() => setShowFactors((s) => !s)}
          className="text-[10px] font-semibold text-accent hover:text-accent-hover cursor-pointer flex items-center gap-1"
          aria-expanded={showFactors}
        >
          Why {sig.quality_score}/100 {showFactors ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {showFactors && (
        <div className="px-4 pb-4 space-y-1.5">
          {sig.quality_breakdown?.map((f) => (
            <div key={f.factor} className="flex items-center gap-3">
              <span className="text-[10px] text-text-secondary w-40 flex-shrink-0">{f.factor}</span>
              <div className="flex-1 h-1.5 rounded-full bg-surface overflow-hidden">
                <div
                  className="h-full rounded-full score-bar"
                  style={{ width: `${(f.points / f.max) * 100}%` }}
                />
              </div>
              <span className="font-mono text-[10px] text-text-primary w-12 text-right">{f.points}/{f.max}</span>
            </div>
          ))}
          <div className="text-[10px] text-text-tertiary pt-1.5 space-y-0.5">
            {sig.quality_breakdown?.map((f) => (
              <div key={f.factor}>· {f.note}</div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Signal card — trader attribution + full reasoning
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
      <div className="flex items-center gap-3 p-4 flex-wrap">
        <span className={`flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1.5 rounded-lg flex-shrink-0
          ${isBuy ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}`}>
          {isBuy ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          {sig.direction}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-base font-bold text-text-primary">{sig.pair}</span>
            {sig.quality_score != null && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-surface-hover text-text-secondary font-mono">
                {sig.quality_score}/100
              </span>
            )}
            {sig.conviction === 'HIGH' && (
              <span className="flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full badge-gradient text-white">
                <Crown size={9} /> HIGH CONVICTION ×{sig.confluence}
              </span>
            )}
          </div>
          <div className="text-[10px] text-text-tertiary truncate mt-0.5">
            <span className="text-purple font-semibold">{sig.trader}</span> — {sig.rule}
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-4 flex-shrink-0">
          {[['Entry', sig.entry, 'text-text-primary'], ['Stop', sig.stop_loss, 'text-negative'],
            ['Target', sig.take_profit, 'text-positive'], ['R:R', `1:${sig.risk_reward}`, 'text-accent']].map(([l, v, c]) => (
            <div key={l} className="text-right">
              <div className="text-[9px] text-text-muted uppercase tracking-wider">{l}</div>
              <div className={`font-mono text-xs ${c}`}>{v}</div>
            </div>
          ))}
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

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
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
              {sig.agreeing_legends?.length > 1 && (
                <span className="text-[9px] text-purple">
                  ({sig.agreeing_legends.join(' + ')})
                </span>
              )}
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

          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-lg bg-accent-subtle/40 border border-accent/20 px-3 py-2">
            <div className="flex items-center gap-1.5">
              <Scale size={12} className="text-accent" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-accent">Risk plan</span>
            </div>
            {sig.position && (
              <>
                <span className="font-mono text-[11px] text-text-primary">
                  {Number(sig.position.units).toLocaleString()} units
                </span>
                <span className="font-mono text-[11px] text-text-secondary">
                  risking {sig.risk_pct_used}% (${sig.position.risk_amount})
                </span>
              </>
            )}
            <span className="text-[10px] text-text-secondary">{sig.trailing?.note}</span>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market status board — regime + edge gate per pair
// ─────────────────────────────────────────────────────────────────────────────
function MarketBoard({ regimes, edges }) {
  const pairs = Object.keys(regimes ?? {});
  if (!pairs.length) return null;
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Activity size={14} className="text-cyan" />
        <span className="text-sm font-semibold text-text-primary">Market Read</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">
          regime + trailing edge per pair
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {pairs.map((p) => {
          const reg = regimes[p];
          const edge = edges?.[p];
          const style = REGIME_STYLE[reg.regime] ?? REGIME_STYLE.NO_DATA;
          const gated = edge && !edge.has_edge;
          return (
            <div key={p} className={`rounded-lg border p-2.5 ${gated ? 'border-warning/30 bg-warning-subtle/20' : 'border-border/40 bg-surface/40'}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs font-bold text-text-primary">{p}</span>
                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${style.cls}`}>
                  {style.label}
                </span>
              </div>
              {gated ? (
                <div className="flex items-start gap-1.5 mt-1.5 text-[10px] text-warning leading-snug">
                  <PauseCircle size={11} className="flex-shrink-0 mt-0.5" />
                  Standing aside — trailing PF {edge.trailing_profit_factor} over {edge.trailing_trades} trades. No edge, no trade.
                </div>
              ) : (
                <div className="text-[10px] text-text-tertiary mt-1.5 leading-snug">
                  {reg.detail}
                  {edge?.has_edge && (
                    <span className="text-positive"> · edge OK (PF {edge.trailing_profit_factor})</span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Legends roster
// ─────────────────────────────────────────────────────────────────────────────
function Roster() {
  const [roster, setRoster] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/v1/legends/traders`)
      .then((r) => r.json())
      .then((d) => setRoster(d.roster))
      .catch(() => setRoster(null));
  }, []);

  if (!roster) return null;
  return (
    <div className="glass-card p-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 cursor-pointer"
        aria-expanded={open}
      >
        <Users size={14} className="text-gold" />
        <span className="text-sm font-semibold text-text-primary">The Legends Roster</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">
          {roster.length} encoded rule sets
        </span>
        <span className="ml-auto text-text-secondary">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </span>
      </button>
      {open && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3">
          {roster.map((t) => (
            <div key={t.name} className="rounded-lg bg-surface/50 border border-border/40 p-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-text-primary">{t.name}</span>
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-purple-subtle text-purple">{t.tag}</span>
              </div>
              <div className="text-[10px] text-text-secondary mt-1 leading-relaxed">{t.rule}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Backtest panel (legends ensemble, per-trader breakdown)
// ─────────────────────────────────────────────────────────────────────────────
function BacktestPanel() {
  const [pair, setPair] = useState('EURUSD');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const run = async () => {
    setRunning(true); setError(null);
    try {
      const res = await fetch(`${API}/api/v1/legends/backtest?pair=${pair}&days=180`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(`Backtest unavailable (${e.message}) — backend may be waking up.`);
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
        <span className="text-sm font-semibold text-text-primary">Verify the legends yourself</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">180-day ensemble replay</span>
      </div>
      <p className="text-[11px] text-text-secondary leading-relaxed">
        Same rules, replayed bar-by-bar on real history — with per-trader and per-regime
        breakdowns so you can see exactly which legend earns their seat on each pair.
      </p>
      <div className="flex items-center gap-2">
        <select
          value={pair}
          onChange={(e) => setPair(e.target.value)}
          className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-text-primary cursor-pointer"
          aria-label="Backtest pair"
        >
          {['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD'].map((p) => (
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

          {result.by_trader && (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-text-muted border-b border-border/40">
                    {['Legend', 'Trades', 'Win %', 'Net R'].map((h) => (
                      <th key={h} className="text-left pb-1.5 pr-4 font-medium text-[9px] uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {Object.entries(result.by_trader).map(([name, b]) => (
                    <tr key={name}>
                      <td className="py-1.5 pr-4 font-semibold text-text-primary">{name}</td>
                      <td className="py-1.5 pr-4 font-mono text-text-secondary">{b.trades}</td>
                      <td className="py-1.5 pr-4 font-mono text-text-secondary">{b.win_rate_pct}%</td>
                      <td className={`py-1.5 font-mono font-bold ${b.net_r >= 0 ? 'text-positive' : 'text-negative'}`}>
                        {b.net_r >= 0 ? '+' : ''}{b.net_r}R
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

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
                stroke={result.return_pct >= 0 ? '#34d764' : '#ff5d55'}
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
// PAGE — Legends Mode
// ─────────────────────────────────────────────────────────────────────────────
export default function LipschutzPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/legends/signals`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setOffline(false);
    } catch {
      setData(null);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const signals = data?.signals ?? [];
  const bestTrades = data?.best_trades ?? [];
  const otherSignals = signals.filter((s) => !s.is_best);
  const breaker = data?.circuit_breaker ? data.circuit_breaker_reason : null;

  return (
    <div className="p-4 lg:p-5 min-h-screen space-y-4 max-w-[1100px] mx-auto">

      {/* Header */}
      <motion.div {...fadeUp} transition={{ duration: 0.25 }} className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gold-subtle flex items-center justify-center">
              <Crown size={16} className="text-gold" />
            </div>
            <h1 className="text-xl font-bold text-text-primary">Legends Mode</h1>
            {offline && (
              <span className="px-2 py-0.5 rounded-full bg-warning-subtle text-warning text-[9px] font-bold">
                BACKEND WAKING UP
              </span>
            )}
          </div>
          <p className="text-xs text-text-secondary mt-1 max-w-[620px] leading-relaxed">
            Eight legendary traders' rules scan every pair, score each setup 0–100 on five
            factors, and surface only the <strong className="text-text-primary">1–2 best
            trades</strong> that clear the quality bar. No edge → no trade; nothing elite →
            nothing forced.
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
          ['Risk per trade', '0.75–1% conviction-sized'],
          ['Stops', 'Mandatory + Seykota trail'],
          ['Edge gate', 'No trailing edge → no trade'],
          ['Circuit breaker', '-3% day / -6% week'],
        ].map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <Shield size={11} className="text-gold flex-shrink-0" />
            <span className="text-[10px] text-text-tertiary uppercase tracking-wider">{k}</span>
            <span className="text-[11px] font-semibold text-text-primary">{v}</span>
          </div>
        ))}
      </motion.div>

      {breaker && (
        <div className="flex items-center gap-2 text-xs text-negative bg-negative-subtle border border-negative/30 rounded-lg px-4 py-3">
          <AlertTriangle size={14} className="flex-shrink-0" />
          <span><strong>Circuit breaker active:</strong> {breaker}</span>
        </div>
      )}

      {/* ── BEST TRADES: the 1-2 setups that clear the quality bar ── */}
      {!loading && bestTrades.length > 0 && (
        <div className="space-y-3">
          {bestTrades.map((sig, i) => (
            <BestTradeCard key={`best-${sig.pair}`} sig={sig} rank={i} />
          ))}
        </div>
      )}
      {!loading && data && bestTrades.length === 0 && signals.length > 0 && (
        <div className="flex items-center gap-2 text-[11px] text-text-secondary bg-surface/40 border border-border/50 rounded-lg px-4 py-2.5">
          <Crown size={13} className="text-gold flex-shrink-0" />
          {data.best_trade_note}
        </div>
      )}

      {/* Market read: regimes + edge gates */}
      {data && <MarketBoard regimes={data.regimes} edges={data.edges} />}

      {/* Other signals */}
      <div className="space-y-3">
        {!loading && otherSignals.length > 0 && (
          <div className="flex items-center gap-2 px-1">
            <Zap size={12} className="text-text-tertiary" />
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-tertiary">
              Other setups (below the quality bar)
            </span>
          </div>
        )}
        {loading ? (
          <div className="glass-card p-8 flex items-center justify-center gap-2 text-text-tertiary text-sm">
            <RefreshCw size={14} className="animate-spin" /> Scanning markets against eight legends' rules…
          </div>
        ) : signals.length === 0 && !breaker ? (
          <div className="glass-card p-8 text-center space-y-1">
            <Zap size={18} className="mx-auto text-text-tertiary" />
            <div className="text-sm font-semibold text-text-primary">No setups right now</div>
            <div className="text-[11px] text-text-secondary max-w-[420px] mx-auto">
              {offline
                ? 'Backend is waking up — refresh in a few seconds.'
                : 'Livermore rule in effect: when the rules don\'t line up, the position is no position. Patience is the trade.'}
            </div>
          </div>
        ) : (
          otherSignals.map((sig, i) => <SignalCard key={`${sig.pair}-${i}`} sig={sig} idx={i} />)
        )}

        {data?.suppressed_by_correlation?.length > 0 && (
          <div className="text-[10px] text-text-tertiary px-1">
            {data.suppressed_by_correlation.map((d, i) => (
              <div key={i}>⏸ {d.reason}</div>
            ))}
          </div>
        )}
      </div>

      {/* Roster + Backtest */}
      <Roster />
      <BacktestPanel />

      {/* Honest disclaimer */}
      <div className="flex items-start gap-2 rounded-lg border border-border/60 bg-surface/40 px-4 py-3">
        <AlertTriangle size={13} className="text-warning flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-text-secondary leading-relaxed">
          <strong className="text-text-primary">No system — not even the legends' rules — wins every trade.</strong>{' '}
          These traders were great because they lost small, not because they never lost.
          Backtested stats do not predict future results. Forex carries real risk of loss;
          never risk money you cannot afford to lose, and never exceed the suggested size.
        </p>
      </div>
    </div>
  );
}
