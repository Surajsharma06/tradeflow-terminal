/**
 * Crypto Analysis Page — BTC, ETH, SOL
 *
 * Per-asset: 7-factor confluence analysis, signal trade card,
 * trade journal (localStorage), risk calculator, mindset checklist,
 * weekly performance summary.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bitcoin, TrendingUp, TrendingDown, RefreshCw, AlertTriangle,
  BookOpen, Shield, CheckSquare, Square, ChevronDown, ChevronUp,
  BarChart3, Activity, Zap, Target, Clock, PlusCircle,
  XCircle, Minus, Award, AlertCircle, Info, Scale,
} from 'lucide-react';
import { API } from '../lib/api';

// ── Journal localStorage helpers ──────────────────────────────────────
const JOURNAL_KEY = 'crypto_journal';

function readJournal() {
  try { return JSON.parse(localStorage.getItem(JOURNAL_KEY) || '[]'); }
  catch { return []; }
}
function writeJournal(entries) {
  localStorage.setItem(JOURNAL_KEY, JSON.stringify(entries));
}

// ── Weekly summary from journal ───────────────────────────────────────
function buildWeeklySummary(entries) {
  const cutoff = Date.now() - 7 * 24 * 3600_000;
  const recent = entries.filter(e => new Date(e.logged_at).getTime() >= cutoff && e.status !== 'OPEN');
  if (!recent.length) return null;
  const wins = recent.filter(e => e.status === 'WIN');
  const losses = recent.filter(e => e.status === 'LOSS');
  const avgRR = recent.reduce((s, e) => s + (e.r_achieved || 0), 0) / recent.length;

  // Pattern detection: same mistake_tag appearing 3+ times
  const tagCounts = {};
  losses.forEach(e => {
    if (e.mistake_tag) tagCounts[e.mistake_tag] = (tagCounts[e.mistake_tag] || 0) + 1;
  });
  const repeatedMistake = Object.entries(tagCounts).find(([, c]) => c >= 3);

  return {
    total: recent.length,
    wins: wins.length,
    losses: losses.length,
    win_rate: Math.round((wins.length / recent.length) * 100),
    avg_rr: Math.round(avgRR * 100) / 100,
    repeated_mistake: repeatedMistake ? { tag: repeatedMistake[0], count: repeatedMistake[1] } : null,
  };
}

// ── Sentiment badge ───────────────────────────────────────────────────
function FearGreedBadge({ fg }) {
  if (!fg) return null;
  const v = fg.value;
  const [cls, ring] = v >= 75 ? ['text-negative', 'border-negative/40']
    : v >= 55 ? ['text-warning', 'border-warning/40']
    : v >= 45 ? ['text-text-secondary', 'border-border']
    : v >= 25 ? ['text-info', 'border-info/40']
    : ['text-positive', 'border-positive/40'];
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${ring} bg-surface/60`}>
      <div className={`text-[10px] font-bold ${cls}`}>Fear & Greed</div>
      <div className={`font-mono text-xs font-bold ${cls}`}>{v}</div>
      <div className="text-[9px] text-text-muted">{fg.label}</div>
    </div>
  );
}

// ── Trend direction chip ──────────────────────────────────────────────
function TrendChip({ trend }) {
  const map = {
    STRONG_BULLISH: { label: '↑↑ Strong Bull', cls: 'text-positive bg-positive-subtle' },
    BULLISH:        { label: '↑ Bullish',       cls: 'text-positive bg-positive-subtle' },
    NEUTRAL:        { label: '→ Neutral',        cls: 'text-text-secondary bg-surface' },
    BEARISH:        { label: '↓ Bearish',       cls: 'text-negative bg-negative-subtle' },
    STRONG_BEARISH: { label: '↓↓ Strong Bear', cls: 'text-negative bg-negative-subtle' },
  };
  const s = map[trend] || map.NEUTRAL;
  return (
    <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${s.cls}`}>{s.label}</span>
  );
}

// ── Indicator mini-pill ───────────────────────────────────────────────
function Pill({ label, value, bullish, bearish }) {
  const cls = bullish ? 'text-positive bg-positive-subtle' : bearish ? 'text-negative bg-negative-subtle' : 'text-text-secondary bg-surface';
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${cls}`}>
      <span className="text-[9px] font-semibold uppercase tracking-wide">{label}</span>
      <span className="font-mono text-[10px] font-bold">{value}</span>
    </div>
  );
}

// ── Signal Trade Card ─────────────────────────────────────────────────
function SignalTradeCard({ signal, symbol, onLog }) {
  const [showChecklist, setShowChecklist] = useState(false);
  const [checks, setChecks] = useState({
    trend: false, rr: false, size: false,
    revenge: false, news: false, emotion: false,
  });

  if (!signal) return null;
  const isLong = signal.direction === 'LONG';
  const allChecked = Object.values(checks).every(Boolean);

  const CHECKLIST_ITEMS = [
    { key: 'trend',   label: 'Trade aligns with higher timeframe trend' },
    { key: 'rr',      label: `Risk:Reward is minimum 1:2 (this setup: 1:${signal.risk_reward_1})` },
    { key: 'size',    label: 'Position size calculated using 1-2% rule, not gut feeling' },
    { key: 'revenge', label: 'Not revenge trading — no recent stopped-out loss in last 30 min' },
    { key: 'news',    label: 'Not entering within 30 min of major macro news event' },
    { key: 'emotion', label: '"Am I trading the system or my feelings?" — confirmed: the system' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border-2 overflow-hidden"
      style={{
        borderColor: isLong ? 'rgba(52,215,100,0.4)' : 'rgba(255,93,85,0.4)',
        background: isLong
          ? 'linear-gradient(135deg, rgba(52,215,100,0.05), transparent)'
          : 'linear-gradient(135deg, rgba(255,93,85,0.05), transparent)',
      }}
    >
      {/* Header */}
      <div className={`flex items-center gap-2 px-4 py-2.5 border-b ${isLong ? 'border-positive/20 bg-positive-subtle/20' : 'border-negative/20 bg-negative-subtle/20'}`}>
        {isLong ? <TrendingUp size={14} className="text-positive" />
                : <TrendingDown size={14} className="text-negative" />}
        <span className={`text-[11px] font-black uppercase tracking-widest ${isLong ? 'text-positive' : 'text-negative'}`}>
          {signal.direction} Signal — {symbol}
        </span>
        <span className="ml-auto text-[9px] text-text-muted bg-surface px-2 py-0.5 rounded-full">
          {signal.timeframe}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {/* Price levels grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {[
            ['Asset', symbol, 'text-text-primary'],
            ['Direction', signal.direction, isLong ? 'text-positive' : 'text-negative'],
            ['Entry', `$${signal.entry.toLocaleString()}`, 'text-text-primary'],
            ['Stop Loss', `$${signal.stop_loss.toLocaleString()}`, 'text-negative'],
            ['TP1 (1:2)', `$${signal.take_profit_1.toLocaleString()}`, 'text-positive'],
            ['TP2 (1:3)', `$${signal.take_profit_2.toLocaleString()}`, 'text-positive'],
          ].map(([l, v, c]) => (
            <div key={l} className="rounded-xl bg-surface/60 border border-border/40 p-2.5 text-center">
              <div className="text-[8px] text-text-muted uppercase tracking-wider mb-1">{l}</div>
              <div className={`font-mono text-xs font-bold ${c}`}>{v}</div>
            </div>
          ))}
        </div>

        {/* R:R + Confluence + Position */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-subtle border border-accent/20">
            <Scale size={11} className="text-accent" />
            <span className="text-[10px] text-text-secondary">R:R</span>
            <span className="font-mono text-xs font-bold text-accent">1:{signal.risk_reward_1} / 1:{signal.risk_reward_2}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-purple-subtle/30 border border-purple/20">
            <Activity size={11} className="text-purple" />
            <span className="text-[10px] text-text-secondary">Confluence</span>
            <span className="font-mono text-xs font-bold text-purple">{signal.confluence_score}</span>
          </div>
          {signal.position_size && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-border/40">
              <Shield size={11} className="text-gold" />
              <span className="text-[10px] text-text-secondary">
                {signal.position_size.units.toFixed(6)} units · ${signal.position_size.risk_amount} at risk
              </span>
            </div>
          )}
        </div>

        {/* Confidence note */}
        <div className="flex items-start gap-2 rounded-xl bg-surface/40 border border-border/30 px-3 py-2">
          <Info size={11} className="text-accent flex-shrink-0 mt-0.5" />
          <span className="text-[11px] text-text-secondary">{signal.confidence_note}</span>
        </div>

        {/* Reasons */}
        <div className="rounded-xl bg-surface/50 border border-border/30 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <BookOpen size={11} className="text-accent" />
            <span className="text-[9px] font-bold uppercase tracking-wider text-text-secondary">Why this signal fired</span>
          </div>
          <ul className="space-y-1">
            {signal.reasons.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-[11px] text-text-secondary">
                <span className={`flex-shrink-0 w-1 h-1 rounded-full mt-1.5 ${r.startsWith('⚠️') ? 'bg-warning' : isLong ? 'bg-positive' : 'bg-negative'}`} />
                {r}
              </li>
            ))}
          </ul>
        </div>

        {/* Trade Checklist + Log */}
        <div>
          <button
            onClick={() => setShowChecklist(s => !s)}
            className="w-full flex items-center gap-2 rounded-xl border border-accent/30 bg-accent-subtle/20 px-4 py-2.5 text-left cursor-pointer hover:bg-accent-subtle/30 transition-colors"
          >
            <CheckSquare size={13} className="text-accent" />
            <span className="text-[11px] font-bold text-accent">Top Trader Mindset Checklist</span>
            <span className="text-[9px] text-text-muted ml-1">— confirm before executing</span>
            <span className="ml-auto text-text-secondary">{showChecklist ? <ChevronUp size={13} /> : <ChevronDown size={13} />}</span>
          </button>

          <AnimatePresence>
            {showChecklist && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="mt-2 space-y-2 p-3 rounded-xl bg-surface/40 border border-border/30">
                  {CHECKLIST_ITEMS.map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => setChecks(c => ({ ...c, [key]: !c[key] }))}
                      className="w-full flex items-start gap-2.5 text-left cursor-pointer group"
                    >
                      {checks[key]
                        ? <CheckSquare size={13} className="text-positive flex-shrink-0 mt-0.5" />
                        : <Square size={13} className="text-text-tertiary flex-shrink-0 mt-0.5 group-hover:text-text-secondary" />
                      }
                      <span className={`text-[11px] leading-relaxed ${checks[key] ? 'text-text-secondary line-through' : 'text-text-primary'}`}>
                        {label}
                      </span>
                    </button>
                  ))}

                  <motion.button
                    whileTap={{ scale: 0.96 }}
                    onClick={() => allChecked && onLog(signal)}
                    disabled={!allChecked}
                    className={`w-full mt-2 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                      allChecked
                        ? 'btn-gradient text-white'
                        : 'bg-surface-hover text-text-muted cursor-not-allowed opacity-50'
                    }`}
                  >
                    {allChecked ? '✓ All checks passed — Log this trade to journal' : `Complete checklist (${Object.values(checks).filter(Boolean).length}/6 done)`}
                  </motion.button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

// ── Indicators panel ──────────────────────────────────────────────────
function IndicatorsPanel({ ind, trend_1h, trend_4h }) {
  if (!ind) return null;
  const { ema: e, rsi, macd, bollinger, vwap_24h, volume_ratio, volume_spike, atr, fibonacci } = ind;
  return (
    <div className="space-y-3">
      {/* EMA */}
      <div className="glass-card p-3">
        <div className="flex items-center gap-2 mb-2">
          <Activity size={12} className="text-accent" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">EMA Alignment</span>
          <TrendChip trend={trend_1h} />
        </div>
        <div className="flex flex-wrap gap-2">
          {e.e9   && <Pill label="EMA 9"   value={`$${e.e9.toLocaleString()}`}   bullish={trend_1h === 'BULLISH'} bearish={trend_1h === 'BEARISH'} />}
          {e.e21  && <Pill label="EMA 21"  value={`$${e.e21.toLocaleString()}`}  bullish={trend_1h === 'BULLISH'} bearish={trend_1h === 'BEARISH'} />}
          {e.e50  && <Pill label="EMA 50"  value={`$${e.e50.toLocaleString()}`}  />}
          {e.e200 && <Pill label="EMA 200" value={`$${e.e200.toLocaleString()}`} />}
        </div>
      </div>

      {/* RSI + MACD */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="glass-card p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">RSI (14)</span>
            <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
              rsi.value >= 70 ? 'bg-negative-subtle text-negative'
              : rsi.value <= 30 ? 'bg-positive-subtle text-positive'
              : 'bg-surface text-text-secondary'
            }`}>
              {rsi.value >= 70 ? 'Overbought' : rsi.value <= 30 ? 'Oversold' : 'Neutral'}
            </span>
          </div>
          <div className="font-mono text-2xl font-black text-text-primary">{rsi.value}</div>
          {rsi.divergence !== 'NONE' && (
            <div className={`text-[9px] font-bold mt-1 ${rsi.divergence.startsWith('BULL') ? 'text-positive' : 'text-negative'}`}>
              {rsi.divergence === 'BULLISH_DIVERGENCE' ? '↗ Bullish divergence' : '↘ Bearish divergence'}
            </div>
          )}
          {/* RSI bar */}
          <div className="mt-2 h-1.5 rounded-full bg-surface overflow-hidden">
            <div
              className={`h-full rounded-full ${rsi.value >= 70 ? 'bg-negative' : rsi.value <= 30 ? 'bg-positive' : 'bg-accent'}`}
              style={{ width: `${rsi.value}%` }}
            />
          </div>
        </div>

        <div className="glass-card p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">MACD (12,26,9)</span>
            {macd.cross !== 'NONE' && (
              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${macd.cross === 'BULLISH_CROSS' ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}`}>
                {macd.cross === 'BULLISH_CROSS' ? '⚡ Bull cross' : '⚡ Bear cross'}
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-2">
            <span className={`font-mono text-xl font-black ${macd.bullish ? 'text-positive' : 'text-negative'}`}>
              {macd.histogram > 0 ? '+' : ''}{macd.histogram}
            </span>
            <span className="text-[9px] text-text-muted">histogram</span>
          </div>
          <div className="text-[10px] text-text-tertiary mt-1">
            Line {macd.line} · Signal {macd.signal_line}
          </div>
        </div>
      </div>

      {/* Bollinger + Volume */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="glass-card p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Bollinger Bands</span>
            {bollinger.squeeze && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-warning-subtle text-warning">
                🔥 SQUEEZE
              </span>
            )}
          </div>
          <div className="flex flex-col gap-0.5 text-[11px]">
            <div className="flex justify-between">
              <span className="text-text-muted">Upper</span>
              <span className="font-mono text-negative">${bollinger.upper.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Middle</span>
              <span className="font-mono text-text-primary">${bollinger.middle.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Lower</span>
              <span className="font-mono text-positive">${bollinger.lower.toLocaleString()}</span>
            </div>
          </div>
        </div>

        <div className="glass-card p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-text-secondary mb-2">Volume + VWAP</div>
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-text-muted">Volume ratio</span>
              <span className={`font-mono text-xs font-bold ${volume_spike ? 'text-warning' : 'text-text-primary'}`}>
                {volume_ratio}× {volume_spike && '⚡ SPIKE'}
              </span>
            </div>
            {vwap_24h && (
              <div className="flex justify-between items-center">
                <span className="text-[10px] text-text-muted">24H VWAP</span>
                <span className="font-mono text-xs text-text-primary">${vwap_24h.toLocaleString()}</span>
              </div>
            )}
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-text-muted">ATR(14)</span>
              <span className="font-mono text-xs text-text-secondary">${atr.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Fibonacci */}
      <div className="glass-card p-3">
        <div className="text-[10px] font-bold uppercase tracking-wider text-text-secondary mb-2">
          Auto Fibonacci — Last 100 bars
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {Object.entries(fibonacci || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between items-center text-[11px]">
              <span className="text-text-muted">{k.replace('_', ' ').replace('fib ', '')} Fib</span>
              <span className="font-mono text-text-primary">${Number(v).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Confluence summary panel ──────────────────────────────────────────
function ConfluencePanel({ conf }) {
  if (!conf) return null;
  const { bullish, bearish, active_direction, active_score, bull_score, bear_score } = conf;
  const maxScore = Math.max(bull_score, bear_score);
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Target size={13} className="text-purple" />
        <span className="text-sm font-semibold text-text-primary">Confluence Score</span>
        <span className={`text-[11px] font-black px-2.5 py-1 rounded-lg ml-auto ${
          active_direction ? (active_direction === 'LONG' ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative')
          : 'bg-surface text-text-secondary'
        }`}>
          {active_direction ? `${active_direction} — ${active_score}/7` : `${maxScore}/7 — No signal`}
        </span>
      </div>

      {active_direction ? (
        <div className="space-y-1.5">
          <p className="text-[10px] text-text-tertiary">
            {active_score >= 5 ? 'Strong alignment across 5+ factors — high confidence' :
             active_score >= 4 ? 'Good 4-factor alignment — medium-high confidence' :
             'Minimum 3-factor confluence met — use smaller size'}
          </p>
          {(active_direction === 'LONG' ? bullish : bearish).map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px] text-text-secondary">
              <span className={`w-1 h-1 rounded-full flex-shrink-0 mt-1.5 ${active_direction === 'LONG' ? 'bg-positive' : 'bg-negative'}`} />
              {c}
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-positive font-semibold w-16">Bull {bull_score}/7</span>
            <div className="flex-1 h-2 rounded-full bg-surface overflow-hidden">
              <div className="h-full bg-positive rounded-full" style={{ width: `${(bull_score / 7) * 100}%` }} />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-negative font-semibold w-16">Bear {bear_score}/7</span>
            <div className="flex-1 h-2 rounded-full bg-surface overflow-hidden">
              <div className="h-full bg-negative rounded-full" style={{ width: `${(bear_score / 7) * 100}%` }} />
            </div>
          </div>
          <p className="text-[10px] text-text-tertiary pt-1">
            Need ≥3 confluences + 4H/1H trend agreement to trigger a signal.
            {bull_score >= 2 || bear_score >= 2 ? ' Building up — check back.' : ' Market is mixed.'}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Trade Journal ─────────────────────────────────────────────────────
const MISTAKE_TAGS = [
  'Counter-trend entry', 'No volume confirmation', 'Ignored stop loss',
  'FOMO entry', 'Oversized position', 'News-time entry', 'Revenge trade',
  'Poor R:R accepted',
];

function JournalModal({ entry, onClose, onSave }) {
  const [status, setStatus] = useState(entry?.status || 'OPEN');
  const [exitPrice, setExitPrice] = useState(entry?.exit_price || '');
  const [mistakeTag, setMistakeTag] = useState(entry?.mistake_tag || '');
  const [notes, setNotes] = useState(entry?.notes || '');

  const rAchieved = (() => {
    if (!exitPrice || !entry) return null;
    const ep = parseFloat(exitPrice);
    const risk = Math.abs(entry.entry - entry.sl);
    if (risk <= 0) return null;
    return entry.direction === 'LONG'
      ? ((ep - entry.entry) / risk)
      : ((entry.entry - ep) / risk);
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="relative z-10 w-full max-w-md glass-card p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <span className="font-bold text-text-primary">Close Trade — {entry?.symbol} {entry?.direction}</span>
          <button onClick={onClose} className="text-text-tertiary hover:text-text-secondary cursor-pointer"><XCircle size={18} /></button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-semibold uppercase text-text-muted block mb-1">Outcome</label>
            <div className="flex gap-2">
              {['WIN', 'LOSS', 'BREAKEVEN'].map(s => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    status === s
                      ? s === 'WIN' ? 'bg-positive text-white'
                        : s === 'LOSS' ? 'bg-negative text-white'
                        : 'bg-accent text-white'
                      : 'bg-surface text-text-secondary hover:bg-surface-hover'
                  }`}
                >{s}</button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-[10px] font-semibold uppercase text-text-muted block mb-1">Exit Price</label>
            <input
              type="number"
              value={exitPrice}
              onChange={e => setExitPrice(e.target.value)}
              className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
              placeholder="e.g. 45200"
            />
            {rAchieved !== null && (
              <span className={`text-[10px] mt-1 block ${rAchieved >= 0 ? 'text-positive' : 'text-negative'}`}>
                R achieved: {rAchieved >= 0 ? '+' : ''}{rAchieved.toFixed(2)}R
              </span>
            )}
          </div>

          {status === 'LOSS' && (
            <div>
              <label className="text-[10px] font-semibold uppercase text-text-muted block mb-1">Mistake Tag (for pattern tracking)</label>
              <select
                value={mistakeTag}
                onChange={e => setMistakeTag(e.target.value)}
                className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-text-primary cursor-pointer"
              >
                <option value="">No specific mistake</option>
                {MISTAKE_TAGS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          )}

          <div>
            <label className="text-[10px] font-semibold uppercase text-text-muted block mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-xs text-text-primary resize-none outline-none focus:border-accent"
              placeholder="What did you learn?"
            />
          </div>
        </div>

        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => onSave({ status, exit_price: exitPrice ? parseFloat(exitPrice) : null, mistake_tag: mistakeTag, notes, r_achieved: rAchieved })}
          className="w-full btn-gradient text-white text-sm font-bold py-2.5 rounded-xl cursor-pointer"
        >
          Save to Journal
        </motion.button>
      </motion.div>
    </div>
  );
}

function JournalPanel({ symbol, journal, setJournal }) {
  const [editEntry, setEditEntry] = useState(null);
  const [filter, setFilter] = useState('ALL');

  const entries = journal.filter(e => e.symbol === symbol);
  const filtered = filter === 'ALL' ? entries : entries.filter(e => e.status === filter);

  const updateEntry = (id, updates) => {
    const next = journal.map(e => e.id === id ? { ...e, ...updates } : e);
    writeJournal(next);
    setJournal(next);
    setEditEntry(null);
  };

  const deleteEntry = (id) => {
    const next = journal.filter(e => e.id !== id);
    writeJournal(next);
    setJournal(next);
  };

  if (!entries.length) {
    return (
      <div className="glass-card p-6 text-center text-text-tertiary">
        <BookOpen size={20} className="mx-auto mb-2" />
        <p className="text-sm">No trades logged for {symbol} yet.</p>
        <p className="text-[10px] mt-1">Use the signal card above to log trades.</p>
      </div>
    );
  }

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen size={13} className="text-accent" />
          <span className="text-sm font-semibold text-text-primary">{symbol} Journal</span>
          <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">{entries.length} trades</span>
        </div>
        <div className="flex gap-1">
          {['ALL', 'OPEN', 'WIN', 'LOSS'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`text-[9px] font-bold px-2 py-1 rounded-lg cursor-pointer ${filter === f ? 'badge-gradient text-white' : 'bg-surface text-text-secondary hover:text-text-primary'}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        {filtered.map(e => (
          <div key={e.id} className="flex items-start gap-3 rounded-xl border border-border/40 bg-surface/40 p-3">
            <div className={`flex-shrink-0 w-2 h-2 rounded-full mt-1.5 ${
              e.status === 'WIN' ? 'bg-positive' : e.status === 'LOSS' ? 'bg-negative'
              : e.status === 'BREAKEVEN' ? 'bg-accent' : 'bg-warning'}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-[10px] font-bold ${e.direction === 'LONG' ? 'text-positive' : 'text-negative'}`}>{e.direction}</span>
                <span className="font-mono text-[11px] text-text-primary">Entry ${e.entry?.toLocaleString()}</span>
                <span className="text-[10px] text-text-muted">SL ${e.sl?.toLocaleString()}</span>
                {e.r_achieved !== null && e.r_achieved !== undefined && (
                  <span className={`font-mono text-[10px] font-bold ${e.r_achieved >= 0 ? 'text-positive' : 'text-negative'}`}>
                    {e.r_achieved >= 0 ? '+' : ''}{e.r_achieved?.toFixed(2)}R
                  </span>
                )}
                {e.mistake_tag && (
                  <span className="text-[9px] bg-negative-subtle text-negative px-1.5 py-0.5 rounded-full">{e.mistake_tag}</span>
                )}
              </div>
              <div className="text-[9px] text-text-muted mt-0.5">{new Date(e.logged_at).toLocaleDateString()} · {e.confluence_score}</div>
              {e.notes && <div className="text-[10px] text-text-secondary mt-1 italic">"{e.notes}"</div>}
            </div>
            <div className="flex gap-1 flex-shrink-0">
              {e.status === 'OPEN' && (
                <button onClick={() => setEditEntry(e)} className="text-[10px] px-2 py-1 rounded-lg bg-surface-hover text-text-secondary hover:text-text-primary cursor-pointer">
                  Close
                </button>
              )}
              <button onClick={() => deleteEntry(e.id)} className="text-[10px] p-1 rounded-lg text-text-muted hover:text-negative cursor-pointer">
                <XCircle size={12} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {editEntry && (
        <JournalModal
          entry={editEntry}
          onClose={() => setEditEntry(null)}
          onSave={(updates) => updateEntry(editEntry.id, updates)}
        />
      )}
    </div>
  );
}

// ── Weekly Summary ────────────────────────────────────────────────────
function WeeklySummary({ journal }) {
  const summary = buildWeeklySummary(journal);
  if (!summary) return null;
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Award size={14} className="text-gold" />
        <span className="text-sm font-semibold text-text-primary">Weekly Summary</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">Last 7 days</span>
      </div>
      <div className="grid grid-cols-4 gap-2 mb-3">
        {[
          ['Trades', summary.total, 'text-text-primary'],
          ['Win Rate', `${summary.win_rate}%`, summary.win_rate >= 55 ? 'text-positive' : 'text-warning'],
          ['Wins', summary.wins, 'text-positive'],
          ['Avg R', `${summary.avg_rr >= 0 ? '+' : ''}${summary.avg_rr}R`, summary.avg_rr >= 0 ? 'text-positive' : 'text-negative'],
        ].map(([l, v, c]) => (
          <div key={l} className="bg-surface/60 rounded-xl p-2.5 text-center">
            <div className="text-[9px] text-text-muted uppercase tracking-wider">{l}</div>
            <div className={`font-mono text-sm font-bold ${c}`}>{v}</div>
          </div>
        ))}
      </div>
      {summary.repeated_mistake && (
        <div className="flex items-start gap-2 rounded-xl bg-warning-subtle border border-warning/30 px-3 py-2">
          <AlertCircle size={13} className="text-warning flex-shrink-0 mt-0.5" />
          <span className="text-[11px] text-warning">
            ⚠️ Repeated mistake pattern: "<strong>{summary.repeated_mistake.tag}</strong>" appeared {summary.repeated_mistake.count} times this week.
            Review your entries before the next trade.
          </span>
        </div>
      )}
    </div>
  );
}

// ── Quick Forex-style Signal Card (shown at top for all active signals) ──
const ASSET_ICONS_MAP = { BTC: '₿', ETH: 'Ξ', SOL: '◎' };

function QuickTradeCard({ symbol, signal, price, expanded, onToggle }) {
  const isLong = signal.direction === 'LONG';
  const riskAmt = Math.abs(signal.entry - signal.stop_loss);
  const rr1 = signal.risk_reward_1 || (riskAmt > 0 ? Math.round(Math.abs(signal.take_profit_1 - signal.entry) / riskAmt * 10) / 10 : '?');
  const rr2 = signal.risk_reward_2 || (riskAmt > 0 ? Math.round(Math.abs(signal.take_profit_2 - signal.entry) / riskAmt * 10) / 10 : '?');
  const fmt = (n) => n != null ? `$${Number(n).toLocaleString()}` : '—';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass-card overflow-hidden border transition-all duration-300 ${isLong ? 'border-positive/35' : 'border-negative/35'}`}
      style={{ boxShadow: isLong ? '0 0 20px rgba(63,185,80,0.08)' : '0 0 20px rgba(248,81,73,0.08)' }}
    >
      <div className="p-4 cursor-pointer hover:bg-surface-hover/20 transition-colors" onClick={onToggle}>
        <div className="flex items-start justify-between gap-3">
          {/* Left: badge + asset */}
          <div className="flex items-center gap-3 min-w-0">
            <div className={`px-3 py-1.5 rounded-lg font-bold text-sm flex-shrink-0 ${isLong ? 'bg-positive text-white' : 'bg-negative text-white'}`}>
              {isLong ? '▲ BUY' : '▼ SELL'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-2xl leading-none">{ASSET_ICONS_MAP[symbol]}</span>
                <span className="text-base font-bold font-mono text-text-primary">{symbol}/USDT</span>
                {signal.confluence_score && (
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-purple-subtle/40 text-purple">
                    {signal.confluence_score}
                  </span>
                )}
              </div>
              <div className="text-[10px] text-text-muted mt-0.5">{signal.timeframe || '4H trend / 1H entry'}</div>
            </div>
          </div>
          {/* Right: current price + expand */}
          <div className="text-right flex-shrink-0">
            <div className="font-mono text-lg font-bold text-text-primary">{fmt(price)}</div>
            <div className="text-[9px] text-text-muted">Current Price</div>
            <ChevronDown size={13} className={`text-text-muted mt-1 ml-auto transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </div>
        </div>

        {/* Entry / SL / TP row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
          {[
            { label: 'ENTRY',          val: fmt(signal.entry),          color: 'text-text-primary' },
            { label: 'STOP LOSS',      val: fmt(signal.stop_loss),      color: 'text-negative'     },
            { label: 'TP1 (1:2)',      val: fmt(signal.take_profit_1),  color: 'text-positive'     },
            { label: `TP2  R:R 1:${rr2}`, val: fmt(signal.take_profit_2), color: 'text-positive'  },
          ].map(({ label, val, color }) => (
            <div key={label} className="rounded-lg bg-surface/60 p-2 text-center">
              <div className="text-[9px] text-text-muted mb-0.5">{label}</div>
              <div className={`font-mono text-xs font-bold ${color}`}>{val}</div>
            </div>
          ))}
        </div>

        {signal.position_size && (
          <div className="flex items-center gap-2 mt-2 text-[10px] text-text-secondary">
            <Shield size={10} className="text-gold" />
            Position: <span className="font-mono font-bold">{signal.position_size.units.toFixed(6)} units</span>
            · Risk: <span className="font-mono font-bold text-warning">${signal.position_size.risk_amount}</span>
          </div>
        )}
      </div>

      {/* Expanded reasons */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden border-t border-border/30"
          >
            <div className="p-4 bg-surface/30 space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-text-secondary flex items-center gap-1.5">
                <Info size={9} /> Why this signal fired
              </div>
              <ul className="space-y-1">
                {signal.reasons?.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-text-secondary">
                    <span className={`w-1 h-1 rounded-full flex-shrink-0 mt-1.5 ${isLong ? 'bg-positive' : 'bg-negative'}`} />
                    {r}
                  </li>
                ))}
              </ul>
              {signal.confidence_note && (
                <div className="flex items-start gap-2 rounded-lg bg-surface/40 px-3 py-2 mt-2">
                  <AlertCircle size={10} className="text-accent flex-shrink-0 mt-0.5" />
                  <span className="text-[11px] text-text-secondary">{signal.confidence_note}</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Asset Price Header ────────────────────────────────────────────────
const ASSET_ICONS = {
  BTC: '₿',
  ETH: 'Ξ',
  SOL: '◎',
};

function AssetHeader({ asset, symbol }) {
  if (!asset || asset.error) {
    return (
      <div className="flex items-center gap-3 p-4 glass-card">
        <span className="text-2xl">{ASSET_ICONS[symbol]}</span>
        <div>
          <div className="font-bold text-text-primary">{symbol}</div>
          <div className="text-xs text-negative">{asset?.error || 'Data unavailable'}</div>
        </div>
      </div>
    );
  }

  const hasSig = !!asset.signal;
  const dir = asset.signal?.direction;

  return (
    <div className="glass-card p-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-2xl font-black"
            style={{ background: 'linear-gradient(135deg, rgba(77,159,255,0.2), rgba(180,140,255,0.2))' }}>
            {ASSET_ICONS[symbol]}
          </div>
          <div>
            <div className="text-xl font-black text-text-primary">{symbol}</div>
            <div className="text-[11px] text-text-muted">{asset.name}</div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1.5">
          <div className="font-mono text-3xl font-black text-text-primary">
            ${asset.price.toLocaleString()}
          </div>
          <div className="flex items-center gap-2">
            <TrendChip trend={asset.trend_4h} />
            {hasSig && (
              <span className={`text-[9px] font-black px-2 py-0.5 rounded-full ${
                dir === 'LONG' ? 'bg-positive text-white' : 'bg-negative text-white'
              }`}>
                ⚡ {dir} SIGNAL
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Quick stats row */}
      <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-border/30">
        <Pill label="RSI" value={asset.indicators?.rsi?.value}
          bullish={asset.indicators?.rsi?.value > 50 && asset.indicators?.rsi?.value < 70}
          bearish={asset.indicators?.rsi?.value < 50 && asset.indicators?.rsi?.value > 30} />
        <Pill label="MACD" value={asset.indicators?.macd?.bullish ? '↑ Bull' : '↓ Bear'}
          bullish={asset.indicators?.macd?.bullish} bearish={!asset.indicators?.macd?.bullish} />
        {asset.indicators?.bollinger?.squeeze && (
          <span className="text-[9px] font-bold px-2 py-1 rounded-lg bg-warning-subtle text-warning">🔥 BB Squeeze</span>
        )}
        {asset.indicators?.volume_spike && (
          <span className="text-[9px] font-bold px-2 py-1 rounded-lg bg-accent-subtle text-accent">⚡ Vol Spike {asset.indicators?.volume_ratio}×</span>
        )}
        <span className="text-[10px] text-text-muted ml-auto">
          {asset.indicators?.rsi?.divergence !== 'NONE' ? (
            <span className={asset.indicators?.rsi?.divergence.startsWith('BULL') ? 'text-positive' : 'text-negative'}>
              {asset.indicators?.rsi?.divergence === 'BULLISH_DIVERGENCE' ? '↗ RSI Bull Div' : '↘ RSI Bear Div'}
            </span>
          ) : null}
        </span>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────
const TABS = ['BTC', 'ETH', 'SOL'];

export default function CryptoPage() {
  const [activeTab, setActiveTab] = useState('BTC');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [journal, setJournal] = useState(readJournal);
  const [balance, setBalance] = useState(10000);
  const [riskPct, setRiskPct] = useState(1.0);
  const [showRisk, setShowRisk] = useState(false);
  const [expandedSig, setExpandedSig] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/crypto/signals?balance=${balance}&risk_pct=${riskPct}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      console.error('Crypto fetch failed:', e);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [balance, riskPct]);

  useEffect(() => { load(); }, [load]);

  const logTrade = (signal, symbol) => {
    const entry = {
      id: Date.now().toString(),
      symbol,
      direction: signal.direction,
      entry: signal.entry,
      sl: signal.stop_loss,
      tp1: signal.take_profit_1,
      tp2: signal.take_profit_2,
      rr: signal.risk_reward_1,
      confluence_score: signal.confluence_score,
      reasons: signal.reasons,
      logged_at: new Date().toISOString(),
      status: 'OPEN',
      exit_price: null,
      r_achieved: null,
      mistake_tag: null,
      notes: null,
    };
    const next = [entry, ...journal];
    writeJournal(next);
    setJournal(next);
  };

  const asset = data?.assets?.[activeTab];
  const fg = data?.fear_greed;

  return (
    <div className="p-4 lg:p-5 min-h-screen max-w-[1100px] mx-auto space-y-4">

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between flex-wrap gap-3"
      >
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center">
              <Bitcoin size={16} className="text-accent" />
            </div>
            <h1 className="text-xl font-bold text-text-primary">Crypto Analysis</h1>
            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full badge-gradient text-white">BTC · ETH · SOL</span>
          </div>
          <p className="text-xs text-text-secondary mt-1 max-w-[620px] leading-relaxed">
            7-factor confluence analysis — EMA alignment, RSI divergence, MACD, Bollinger Bands,
            VWAP + volume spike, Fibonacci, and market sentiment. Minimum 3/7 required for a signal.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRisk(s => !s)}
            className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary bg-surface border border-border rounded-lg px-3 py-2 cursor-pointer"
          >
            <Shield size={12} /> Risk Settings
          </button>
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={load}
            className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary bg-surface border border-border rounded-lg px-3 py-2 cursor-pointer"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </motion.button>
        </div>
      </motion.div>

      {/* Risk settings */}
      <AnimatePresence>
        {showRisk && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="glass-card p-4 flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-3">
                <label className="text-[10px] font-semibold uppercase text-text-muted">Account Balance ($)</label>
                <input
                  type="number"
                  value={balance}
                  onChange={e => setBalance(parseFloat(e.target.value) || 10000)}
                  className="bg-surface border border-border rounded-lg px-3 py-1.5 text-sm font-mono text-text-primary w-28 outline-none focus:border-accent"
                />
              </div>
              <div className="flex items-center gap-3">
                <label className="text-[10px] font-semibold uppercase text-text-muted">Risk % per trade</label>
                <div className="flex gap-1">
                  {[0.5, 1.0, 1.5, 2.0].map(r => (
                    <button
                      key={r}
                      onClick={() => setRiskPct(r)}
                      className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer ${riskPct === r ? 'btn-gradient text-white' : 'bg-surface text-text-secondary hover:text-text-primary'}`}
                    >{r}%</button>
                  ))}
                </div>
              </div>
              <p className="text-[10px] text-text-muted">Daily loss limit: 3% · Max 2 concurrent positions (BTC+ETH+SOL are correlated — treat as one portfolio)</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Fear & Greed bar ── */}
      {data && (
        <div className="flex flex-wrap items-center gap-3">
          <FearGreedBadge fg={fg} />
          <span className="text-[9px] text-text-muted ml-auto">{data.generated_at?.split('T')[1]?.slice(0,8)} UTC</span>
        </div>
      )}

      {/* ── Active Trade Signals (Forex-style) ── */}
      {data && (() => {
        const activeSigs = ['BTC','ETH','SOL'].filter(s => data.assets?.[s]?.signal);
        return (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Zap size={13} className="text-accent" />
              <span className="text-sm font-semibold text-text-primary">Active Trade Signals</span>
              <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                activeSigs.length > 0 ? 'bg-positive-subtle text-positive' : 'bg-surface text-text-muted'
              }`}>{activeSigs.length} / 3 assets</span>
            </div>
            {activeSigs.length > 0 ? (
              <div className="space-y-3">
                {activeSigs.map(sym => (
                  <QuickTradeCard
                    key={sym}
                    symbol={sym}
                    signal={data.assets[sym].signal}
                    price={data.assets[sym].price}
                    expanded={expandedSig === sym}
                    onToggle={() => setExpandedSig(p => p === sym ? null : sym)}
                  />
                ))}
              </div>
            ) : (
              <div className="glass-card p-6 flex items-center gap-3 text-text-secondary">
                <Activity size={16} className="text-text-muted" />
                <div>
                  <div className="text-sm font-semibold text-text-primary">No trade setups right now</div>
                  <div className="text-[11px] text-text-tertiary mt-0.5">
                    Confluence building — need 3/7 factors + 4H & 1H trend alignment. Check back in 15–30 min.
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* Asset tabs */}
      <div className="flex gap-1 p-1 rounded-xl bg-surface/60 border border-border/40">
        {TABS.map(sym => (
          <button
            key={sym}
            onClick={() => setActiveTab(sym)}
            className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all cursor-pointer ${
              activeTab === sym ? 'btn-gradient text-white shadow-md' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {ASSET_ICONS[sym]} {sym}
            {data?.assets?.[sym]?.signal && (
              <span className="ml-1.5 text-[8px] font-black px-1.5 py-0.5 rounded-full bg-white/20">SIG</span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="glass-card p-12 flex items-center justify-center gap-2 text-text-tertiary">
          <RefreshCw size={15} className="animate-spin" />
          Fetching {activeTab} data and running confluence analysis…
        </div>
      ) : !data ? (
        <div className="glass-card p-8 text-center">
          <AlertTriangle size={20} className="mx-auto text-warning mb-2" />
          <p className="text-sm text-text-secondary">Backend is waking up — try refreshing in a few seconds.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <AssetHeader asset={asset} symbol={activeTab} />

          {asset && !asset.error && (
            <>
              <ConfluencePanel conf={asset.confluence} />

              {asset.signal ? (
                <SignalTradeCard
                  signal={asset.signal}
                  symbol={activeTab}
                  onLog={(sig) => logTrade(sig, activeTab)}
                />
              ) : (
                <div className="glass-card p-6 flex items-center gap-3 text-text-secondary">
                  <Minus size={15} />
                  <div>
                    <div className="text-sm font-semibold text-text-primary">No signal for {activeTab} right now</div>
                    <div className="text-[11px] text-text-tertiary mt-0.5">
                      {asset.confluence.bull_score >= 2 || asset.confluence.bear_score >= 2
                        ? `Confluence building (${Math.max(asset.confluence.bull_score, asset.confluence.bear_score)}/7) — check back. Need 4H + 1H trend alignment.`
                        : 'Market indicators are mixed. Wait for clearer alignment across all timeframes.'}
                    </div>
                  </div>
                </div>
              )}

              <IndicatorsPanel
                ind={asset.indicators}
                trend_1h={asset.trend_1h}
                trend_4h={asset.trend_4h}
              />

              {/* Sentiment detail */}
              <div className="glass-card p-4">
                <div className="text-[10px] font-bold uppercase tracking-wider text-text-secondary mb-3">Sentiment</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="bg-surface/60 rounded-xl border border-border/40 p-3">
                    <div className="text-[10px] text-text-muted mb-1">Fear & Greed Index</div>
                    <div className="font-mono text-2xl font-black text-text-primary">{asset.sentiment?.fear_greed?.value ?? '—'}</div>
                    <div className="text-[11px] text-text-secondary">{asset.sentiment?.fear_greed?.label}</div>
                    <p className="text-[10px] text-text-muted mt-1">
                      {(asset.sentiment?.fear_greed?.value ?? 50) >= 75 ? 'Extreme greed — historically contrarian signal for pullback'
                        : (asset.sentiment?.fear_greed?.value ?? 50) <= 25 ? 'Extreme fear — historically contrarian signal for bounce'
                        : 'Neutral zone — sentiment not extreme'}
                    </p>
                  </div>
                  <div className="bg-surface/60 rounded-xl border border-border/40 p-3">
                    <div className="text-[10px] text-text-muted mb-1">Funding Rate</div>
                    <div className={`font-mono text-xl font-black ${
                      asset.sentiment?.funding?.extreme
                        ? asset.sentiment?.funding?.direction === 'LONG_HEAVY' ? 'text-negative' : 'text-positive'
                        : 'text-text-primary'
                    }`}>
                      {asset.sentiment?.funding?.rate_pct ?? 0}%
                    </div>
                    <div className="text-[11px] text-text-secondary">{asset.sentiment?.funding?.direction?.replace('_', ' ')}</div>
                    {asset.sentiment?.funding?.extreme && (
                      <p className="text-[10px] text-warning mt-1">
                        ⚠️ Extreme funding — {asset.sentiment?.funding?.direction === 'LONG_HEAVY'
                          ? 'longs heavily funded, watch for long squeeze'
                          : 'shorts heavily funded, watch for short squeeze'}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          <WeeklySummary journal={journal} />
          <JournalPanel symbol={activeTab} journal={journal} setJournal={setJournal} />
        </div>
      )}

      {/* Disclaimer */}
      <div className="flex items-start gap-2 rounded-xl border border-border/60 bg-surface/40 px-4 py-3">
        <AlertTriangle size={13} className="text-warning flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-text-secondary leading-relaxed">
          <strong className="text-text-primary">Crypto signals are analysis tools only — not financial advice.</strong>{' '}
          Cryptocurrency markets carry extreme volatility and risk of total capital loss. Manual
          confirmation required before every trade. Never risk money you cannot afford to lose.
          {data?.disclaimer}
        </p>
      </div>
    </div>
  );
}
