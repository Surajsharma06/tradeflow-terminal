import React, { useEffect, useState } from 'react';
import {
  TrendingUp, TrendingDown, BarChart3, Shield, Zap, Activity,
  DollarSign, AlertTriangle, Clock, ArrowUpRight, ArrowDownRight,
  ThumbsUp, ThumbsDown, CheckCircle2, XCircle, RefreshCw,
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// DATA
// ─────────────────────────────────────────────────────────────────────────────

const MARKETS = [
  { name: 'NIFTY 50',   price: 24832.50, change:  1.23, currency: '₹', flag: '🇮🇳', label: 'NSE' },
  { name: 'SENSEX',     price: 81765.30, change:  1.08, currency: '₹', flag: '🇮🇳', label: 'BSE' },
  { name: 'NIFTY BANK', price: 53412.80, change: -0.34, currency: '₹', flag: '🇮🇳', label: 'BANK' },
  { name: 'S&P 500',    price:  5942.18, change:  0.67, currency: '$', flag: '🇺🇸', label: 'NYSE' },
  { name: 'NASDAQ',     price: 19218.45, change:  1.12, currency: '$', flag: '🇺🇸', label: 'NSDQ' },
  { name: 'BTC/USDT',   price: 108432,   change:  2.34, currency: '$', flag: '₿',   label: 'CRPT' },
  { name: 'EUR/USD',    price:   1.1352, change: -0.41, currency: '',  flag: '💱',   label: 'FX'  },
  { name: 'GOLD',       price:  3350.40, change:  0.82, currency: '$', flag: '🥇',   label: 'XAU' },
];

const INITIAL_SIGNALS = [
  { id: 1, pair: 'AUD/USD', dir: 'BUY',  entry: 0.68961, sl: 0.68610, tp: 0.69750, conf: 87, strategy: 'BB+RSI Oversold',   rr: '1:2.1', feedback: null },
  { id: 2, pair: 'USD/CAD', dir: 'SELL', entry: 1.42316, sl: 1.42953, tp: 1.41400, conf: 83, strategy: 'BB+RSI Overbought', rr: '1:1.9', feedback: null },
  { id: 3, pair: 'NZD/USD', dir: 'BUY',  entry: 0.56462, sl: 0.56099, tp: 0.57100, conf: 78, strategy: 'BB+RSI Oversold',   rr: '1:1.8', feedback: null },
  { id: 4, pair: 'EUR/USD', dir: 'SELL', entry: 1.13520, sl: 1.14100, tp: 1.12800, conf: 72, strategy: 'EMA Trend + MACD',  rr: '1:1.2', feedback: null },
];

const POSITIONS = [
  { sym: 'EUR/USD', dir: 'BUY',  entry: 1.1205, cur: 1.1352, pnl: +147, risk: 0.8 },
  { sym: 'USD/JPY', dir: 'SELL', entry: 162.50, cur: 161.77, pnl: +73,  risk: 1.2 },
  { sym: 'NIFTY',  dir: 'BUY',  entry: 24500,  cur: 24832,  pnl: +332, risk: 1.5 },
];

const RISK_BARS = [
  { label: 'Daily Loss Limit',  used: 1.2, max: 3.0,  color: '#3fb950' },
  { label: 'Position Exposure', used: 38,  max: 100,  color: '#388bfd' },
  { label: 'Drawdown',          used: 2.1, max: 10,   color: '#e3b341' },
];

const ASSETS = ['NIFTY', 'S&P', 'BTC', 'Gold', 'Crude', 'DXY', 'EUR/USD'];
const CORR = [
  [ 1.00,  0.72,  0.35,  0.18,  0.42, -0.31,  0.28],
  [ 0.72,  1.00,  0.42,  0.12,  0.38, -0.45,  0.41],
  [ 0.35,  0.42,  1.00, -0.08,  0.22, -0.38,  0.33],
  [ 0.18,  0.12, -0.08,  1.00,  0.25, -0.62,  0.58],
  [ 0.42,  0.38,  0.22,  0.25,  1.00, -0.18,  0.15],
  [-0.31, -0.45, -0.38, -0.62, -0.18,  1.00, -0.88],
  [ 0.28,  0.41,  0.33,  0.58,  0.15, -0.88,  1.00],
];

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function makeSparkline(positive, len = 20) {
  const pts = Array.from({ length: len }, () =>
    Math.random() * 0.6 - (positive ? 0.1 : 0.5)
  );
  const min = Math.min(...pts), max = Math.max(...pts);
  const range = max - min || 1;
  return pts.map((p, i) => ({
    x: (i / (len - 1)) * 72,
    y: 26 - ((p - min) / range) * 26,
  }));
}

function corrColor(v) {
  if (v === 1)    return '#21262d';
  if (v >= 0.6)   return '#da3633';
  if (v >= 0.3)   return '#f85149aa';
  if (v >= 0)     return '#21262d';
  if (v >= -0.3)  return '#388bfdaa';
  return '#1f6feb';
}

// ─────────────────────────────────────────────────────────────────────────────
// MINI COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────

// Sparkline — stable (memoized per item)
function Sparkline({ positive }) {
  // Stable: computed once per mount via lazy useState initializer
  const [pts] = useState(() => makeSparkline(positive));
  const color = positive ? '#3fb950' : '#f85149';
  const d = `M ${pts.map(p => `${p.x},${p.y}`).join(' L ')}`;
  return (
    <svg width={72} height={26} className="opacity-75 flex-shrink-0">
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Market card — emoji flag restored, cleaner layout
function MarketCard({ item, animated }) {
  const up = item.change >= 0;
  return (
    <div
      className={`glass-card p-3 cursor-default group hover:border-border-light transition-all duration-300 ${
        animated ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
      }`}
    >
      {/* Top: flag + label + sparkline */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-base leading-none">{item.flag}</span>
          <span className="text-[9px] font-bold text-text-muted tracking-wider">{item.label}</span>
        </div>
        <Sparkline positive={up} />
      </div>
      {/* Name */}
      <div className="text-[10px] font-medium text-text-secondary truncate mb-0.5">{item.name}</div>
      {/* Price */}
      <div className="font-mono text-sm font-bold text-text-primary">
        {item.currency}
        {item.price > 1000
          ? item.price.toLocaleString('en-IN')
          : item.price.toFixed(item.price < 10 ? 4 : 2)}
      </div>
      {/* Change */}
      <div className={`flex items-center gap-0.5 text-[11px] font-semibold mt-0.5 ${up ? 'text-positive' : 'text-negative'}`}>
        {up ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
        {up ? '+' : ''}{item.change.toFixed(2)}%
      </div>
    </div>
  );
}

// Signal row — with Win/Loss feedback buttons
function SignalRow({ sig, onFeedback }) {
  const isBuy  = sig.dir === 'BUY';
  const confColor = sig.conf >= 80 ? 'var(--color-positive)'
    : sig.conf >= 70 ? 'var(--color-warning)'
    : 'var(--color-negative)';
  const confBg = sig.conf >= 80 ? 'bg-positive-subtle'
    : sig.conf >= 70 ? 'bg-warning-subtle'
    : 'bg-negative-subtle';

  return (
    <div className={`flex items-center gap-3 py-2.5 px-3 rounded-lg transition-all duration-150 cursor-default
      ${sig.feedback === 'win' ? 'bg-positive-subtle/30 border border-positive/20'
        : sig.feedback === 'loss' ? 'bg-negative-subtle/30 border border-negative/20'
        : 'bg-surface/40 hover:bg-surface-hover/60 border border-transparent'}`}
    >
      {/* Direction */}
      <span className={`text-[10px] font-bold px-2 py-1 rounded-md flex-shrink-0 w-10 text-center
        ${isBuy ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}`}>
        {sig.dir}
      </span>

      {/* Pair + strategy */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-bold font-mono text-text-primary leading-tight">{sig.pair}</div>
        <div className="text-[10px] text-text-muted truncate mt-0.5">{sig.strategy}</div>
      </div>

      {/* Entry / SL / TP */}
      <div className="hidden md:flex items-center gap-4 flex-shrink-0">
        <div className="text-right">
          <div className="text-[9px] text-text-muted uppercase tracking-wider">Entry</div>
          <div className="font-mono text-[11px] text-text-primary">{sig.entry.toFixed(5)}</div>
        </div>
        <div className="text-right">
          <div className="text-[9px] text-negative uppercase tracking-wider">SL</div>
          <div className="font-mono text-[11px] text-negative">{sig.sl.toFixed(5)}</div>
        </div>
        <div className="text-right">
          <div className="text-[9px] text-positive uppercase tracking-wider">TP</div>
          <div className="font-mono text-[11px] text-positive">{sig.tp.toFixed(5)}</div>
        </div>
        <div className="text-right">
          <div className="text-[9px] text-text-muted uppercase tracking-wider">R:R</div>
          <div className="font-mono text-[11px] text-accent">{sig.rr}</div>
        </div>
      </div>

      {/* AI Confidence */}
      <div className={`flex-shrink-0 w-14 px-2 py-1.5 rounded-lg ${confBg} text-center`}>
        <div className="text-[9px] text-text-muted mb-0.5">AI</div>
        <div className="text-sm font-bold font-mono" style={{ color: confColor }}>{sig.conf}%</div>
      </div>

      {/* Feedback buttons — bot learns from these */}
      <div className="flex-shrink-0 flex items-center gap-1">
        {sig.feedback === null ? (
          <>
            <button
              onClick={() => onFeedback(sig.id, 'win')}
              title="Mark as Win"
              className="p-1.5 rounded-md hover:bg-positive-subtle text-text-muted hover:text-positive transition-colors cursor-pointer"
            >
              <ThumbsUp size={13} />
            </button>
            <button
              onClick={() => onFeedback(sig.id, 'loss')}
              title="Mark as Loss"
              className="p-1.5 rounded-md hover:bg-negative-subtle text-text-muted hover:text-negative transition-colors cursor-pointer"
            >
              <ThumbsDown size={13} />
            </button>
          </>
        ) : sig.feedback === 'win' ? (
          <CheckCircle2 size={16} className="text-positive" />
        ) : (
          <XCircle size={16} className="text-negative" />
        )}
      </div>
    </div>
  );
}

// Risk gauge — pure SVG
function RiskGauge({ value = 35 }) {
  const angle  = -90 + (value / 100) * 180;
  const color  = value < 30 ? '#3fb950' : value < 60 ? '#e3b341' : '#f85149';
  const label  = value < 30 ? 'LOW RISK' : value < 60 ? 'MODERATE' : 'HIGH RISK';
  const nx = 60 + 35 * Math.cos(((angle - 90) * Math.PI) / 180);
  const ny = 55 + 35 * Math.sin(((angle - 90) * Math.PI) / 180);
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 120 62" className="w-36 h-[72px]">
        <path d="M 10 55 A 50 50 0 0 1 110 55" fill="none" stroke="#21262d" strokeWidth="10" strokeLinecap="round"/>
        <path d="M 10 55 A 50 50 0 0 1 43 15"  fill="none" stroke="#3fb950" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
        <path d="M 43 15 A 50 50 0 0 1 77 15"  fill="none" stroke="#e3b341" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
        <path d="M 77 15 A 50 50 0 0 1 110 55" fill="none" stroke="#f85149" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
        <line x1="60" y1="55" x2={nx} y2={ny} stroke={color} strokeWidth="2.5" strokeLinecap="round"/>
        <circle cx="60" cy="55" r="4" fill={color}/>
      </svg>
      <div className="text-2xl font-bold font-mono" style={{ color }}>{value}%</div>
      <div className="text-[10px] font-bold tracking-widest mt-0.5" style={{ color }}>{label}</div>
    </div>
  );
}

// Correlation heatmap
function CorrHeatmap() {
  return (
    <div className="overflow-x-auto">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `56px repeat(${ASSETS.length}, 1fr)`,
          gap: 2,
          minWidth: 380,
        }}
      >
        <div />
        {ASSETS.map(a => (
          <div key={a} className="text-[9px] text-text-muted text-center font-mono pb-1 truncate">{a}</div>
        ))}
        {CORR.map((row, ri) => (
          <React.Fragment key={`row-${ri}`}>
            <div className="text-[9px] text-text-muted font-mono flex items-center">{ASSETS[ri]}</div>
            {row.map((val, ci) => (
              <div
                key={`${ri}-${ci}`}
                title={`${ASSETS[ri]} vs ${ASSETS[ci]}: ${val.toFixed(2)}`}
                className="rounded-sm flex items-center justify-center font-mono font-bold cursor-default"
                style={{ background: corrColor(val), color: '#e6edf3', height: 28, fontSize: 9 }}
              >
                {val.toFixed(2)}
              </div>
            ))}
          </React.Fragment>
        ))}
      </div>
      <div className="flex items-center justify-center gap-4 mt-3">
        {[['#1f6feb', '−1 Inverse'], ['#21262d', '0 Neutral'], ['#da3633', '+1 Correlated']].map(([c, l]) => (
          <span key={l} className="flex items-center gap-1.5 text-[10px] text-text-muted">
            <span className="w-3 h-2 rounded-sm inline-block" style={{ background: c }} />{l}
          </span>
        ))}
      </div>
    </div>
  );
}

// Bot accuracy tracker — shows learning progress from feedback
function AccuracyTracker({ signals }) {
  const total    = signals.filter(s => s.feedback !== null).length;
  const wins     = signals.filter(s => s.feedback === 'win').length;
  const losses   = signals.filter(s => s.feedback === 'loss').length;
  const winRate  = total > 0 ? Math.round((wins / total) * 100) : null;
  const byStrat  = {};
  signals.forEach(s => {
    if (s.feedback === null) return;
    if (!byStrat[s.strategy]) byStrat[s.strategy] = { w: 0, l: 0 };
    byStrat[s.strategy][s.feedback === 'win' ? 'w' : 'l']++;
  });

  if (total === 0) {
    return (
      <div className="flex items-center gap-2 p-3 rounded-lg bg-accent-subtle/30 border border-accent/20">
        <Zap size={13} className="text-accent flex-shrink-0" />
        <span className="text-[11px] text-text-secondary">
          Signal pe <strong className="text-text-primary">👍 Win</strong> ya <strong className="text-text-primary">👎 Loss</strong> mark karo — bot apni accuracy track karega aur seekhega.
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Overall stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Win Rate', value: winRate !== null ? `${winRate}%` : '—', color: winRate >= 60 ? 'text-positive' : winRate >= 40 ? 'text-warning' : 'text-negative' },
          { label: 'Wins',     value: wins,    color: 'text-positive' },
          { label: 'Losses',   value: losses,  color: 'text-negative' },
        ].map(s => (
          <div key={s.label} className="text-center p-2 rounded-lg bg-surface/50">
            <div className={`text-xl font-bold font-mono ${s.color}`}>{s.value}</div>
            <div className="text-[9px] text-text-muted mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Per-strategy breakdown */}
      {Object.keys(byStrat).length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[9px] text-text-muted uppercase tracking-wider">Strategy Accuracy</div>
          {Object.entries(byStrat).map(([strat, { w, l }]) => {
            const t  = w + l;
            const wr = Math.round((w / t) * 100);
            return (
              <div key={strat} className="flex items-center gap-2">
                <div className="flex-1 text-[10px] text-text-secondary truncate">{strat}</div>
                <div className="text-[10px] font-mono text-text-muted">{w}W / {l}L</div>
                <div className="w-16 h-1.5 bg-surface rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${wr}%`, background: wr >= 60 ? '#3fb950' : wr >= 40 ? '#e3b341' : '#f85149' }}
                  />
                </div>
                <div className="text-[10px] font-bold font-mono w-8 text-right"
                  style={{ color: wr >= 60 ? '#3fb950' : wr >= 40 ? '#e3b341' : '#f85149' }}>
                  {wr}%
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DASHBOARD PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [mounted,  setMounted]  = useState(false);
  const [time,     setTime]     = useState('');
  const [signals,  setSignals]  = useState(INITIAL_SIGNALS);
  const riskVal = 38;

  useEffect(() => {
    const id = setTimeout(() => setMounted(true), 60);
    const tick = () => setTime(
      new Date().toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
      })
    );
    tick();
    const t = setInterval(tick, 1000);
    return () => { clearTimeout(id); clearInterval(t); };
  }, []);

  const handleFeedback = (id, result) => {
    setSignals(prev => prev.map(s => s.id === id ? { ...s, feedback: result } : s));
  };

  const resetFeedback = () => {
    setSignals(prev => prev.map(s => ({ ...s, feedback: null })));
  };

  const buyCount  = signals.filter(s => s.dir === 'BUY').length;
  const sellCount = signals.filter(s => s.dir === 'SELL').length;
  const highConf  = signals.filter(s => s.conf >= 80).length;

  const anim = (delay = '') =>
    `transition-all duration-500 ${delay} ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`;

  return (
    <div className="p-4 lg:p-5 min-h-screen space-y-4">

      {/* ── Header ── */}
      <div className={`flex items-center justify-between flex-wrap gap-3 ${anim()}`}>
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center">
              <BarChart3 size={16} className="text-accent" />
            </div>
            <h1 className="text-xl font-bold text-text-primary">Trading Dashboard</h1>
            <span className="px-2 py-0.5 rounded-full bg-positive-subtle text-positive text-[9px] font-bold animate-pulse">
              ● LIVE
            </span>
          </div>
          <p className="text-xs text-text-muted ml-10 mt-0.5">Market overview • AI Signals • Risk • Correlation</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-text-secondary">
          <Clock size={12} />
          <span className="font-mono">{time} IST</span>
        </div>
      </div>

      {/* ── Stats Bar ── */}
      <div className={`grid grid-cols-2 sm:grid-cols-4 gap-3 ${anim('delay-75')}`}>
        {[
          { label: 'Active Signals', value: signals.length, icon: Zap,        color: '#388bfd' },
          { label: 'High Confidence',value: highConf,       icon: Shield,      color: '#e3b341' },
          { label: 'BUY Signals',    value: buyCount,       icon: TrendingUp,  color: '#3fb950' },
          { label: 'SELL Signals',   value: sellCount,      icon: TrendingDown,color: '#f85149' },
        ].map((s) => (
          <div key={s.label} className="glass-card p-3 flex items-center gap-3 cursor-default hover:border-border-light transition-colors">
            <div className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center" style={{ background: s.color + '22' }}>
              <s.icon size={14} style={{ color: s.color }} />
            </div>
            <div>
              <div className="text-xl font-bold font-mono text-text-primary">{s.value}</div>
              <div className="text-[10px] text-text-muted">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Live Markets ── */}
      <div className={anim('delay-100')}>
        <div className="flex items-center gap-2 mb-2">
          <Activity size={13} className="text-text-secondary" />
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Live Markets</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {MARKETS.map((m, i) => <MarketCard key={i} item={m} animated={mounted} />)}
        </div>
      </div>

      {/* ── Signals + Risk ── */}
      <div className={`grid grid-cols-1 lg:grid-cols-3 gap-4 ${anim('delay-150')}`}>

        {/* AI Signals */}
        <div className="lg:col-span-2 glass-card p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-accent" />
              <span className="text-sm font-semibold text-text-primary">AI Signals</span>
              <span className="text-[9px] bg-accent-subtle text-accent px-2 py-0.5 rounded-full font-bold">LIVE</span>
            </div>
            <a href="/forex" className="text-[10px] text-accent hover:text-accent-hover transition-colors cursor-pointer">
              View all →
            </a>
          </div>

          <div className="space-y-1.5">
            {signals.map(s => (
              <SignalRow key={s.id} sig={s} onFeedback={handleFeedback} />
            ))}
          </div>

          <div className="p-2.5 rounded-lg bg-surface/50 flex items-center gap-2">
            <AlertTriangle size={11} className="text-warning flex-shrink-0" />
            <span className="text-[10px] text-text-muted">
              AI signals only — execute manually on your broker. Never risk &gt;2% per trade.
            </span>
          </div>
        </div>

        {/* Risk Meter */}
        <div className="glass-card p-4 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Shield size={14} className="text-positive" />
            <span className="text-sm font-semibold text-text-primary">Portfolio Risk</span>
          </div>
          <div className="flex items-center justify-center">
            <RiskGauge value={riskVal} />
          </div>
          <div className="space-y-2.5">
            {RISK_BARS.map((r) => (
              <div key={r.label}>
                <div className="flex justify-between text-[10px] text-text-muted mb-1">
                  <span>{r.label}</span>
                  <span style={{ color: r.color }}>{r.used}% / {r.max}%</span>
                </div>
                <div className="h-1.5 bg-surface rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${(r.used / r.max) * 100}%`, background: r.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bot Learning Tracker ── */}
      <div className={`glass-card p-4 ${anim('delay-200')}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp size={14} className="text-purple" />
            <span className="text-sm font-semibold text-text-primary">Bot Signal Accuracy</span>
            <span className="text-[9px] bg-purple-subtle text-purple px-2 py-0.5 rounded-full font-bold">
              LEARNING
            </span>
          </div>
          {signals.some(s => s.feedback !== null) && (
            <button
              onClick={resetFeedback}
              className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text-secondary transition-colors cursor-pointer"
            >
              <RefreshCw size={10} /> Reset
            </button>
          )}
        </div>
        <AccuracyTracker signals={signals} />
      </div>

      {/* ── Open Positions ── */}
      <div className={`glass-card p-4 ${anim('delay-250')}`}>
        <div className="flex items-center gap-2 mb-3">
          <DollarSign size={14} className="text-gold" />
          <span className="text-sm font-semibold text-text-primary">Open Positions</span>
          <span className="text-[9px] text-text-muted bg-surface px-2 py-0.5 rounded-full">Paper Mode</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted border-b border-border/40">
                {['Symbol', 'Dir', 'Entry', 'Current', 'P&L', 'Risk %'].map(h => (
                  <th key={h} className="text-left pb-2 pr-4 font-medium text-[10px] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {POSITIONS.map((p, i) => {
                const pos = p.pnl >= 0;
                return (
                  <tr key={i} className="hover:bg-surface/30 transition-colors cursor-default">
                    <td className="py-2.5 pr-4 font-mono font-bold text-text-primary">{p.sym}</td>
                    <td className="py-2.5 pr-4">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold
                        ${p.dir === 'BUY' ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}`}>
                        {p.dir}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-text-secondary">{p.entry}</td>
                    <td className="py-2.5 pr-4 font-mono text-text-primary">{p.cur}</td>
                    <td className={`py-2.5 pr-4 font-mono font-bold ${pos ? 'text-positive' : 'text-negative'}`}>
                      {pos ? '+' : ''}${p.pnl}
                    </td>
                    <td className="py-2.5 font-mono text-text-secondary">{p.risk}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Correlation Heatmap ── */}
      <div className={`glass-card p-4 ${anim('delay-300')}`}>
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 size={14} className="text-purple" />
          <span className="text-sm font-semibold text-text-primary">Correlation Matrix</span>
          <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">Cross-asset</span>
        </div>
        <CorrHeatmap />
      </div>

    </div>
  );
}
