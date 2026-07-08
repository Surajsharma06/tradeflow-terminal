/**
 * Commodity Analysis Page — Gold (XAU), Silver (XAG), WTI Crude, Natural Gas
 *
 * Each asset has commodity-specific fundamental drivers:
 *   Gold/Silver  → DXY inverse correlation, real yields, FOMC
 *   WTI          → OPEC+ meetings, EIA petroleum storage, backwardation
 *   Natural Gas  → EIA storage, weather seasonality, ATR×2 stops
 *
 * Analysis layers per asset:
 *   Technical    — EMA 9/21/50/200, RSI+divergence, MACD, BB squeeze, VWAP, Fibonacci
 *   COT          — CFTC managed-money positioning (extreme = contrarian; WoW shift = momentum)
 *   Curve        — Contango vs Backwardation (backwardation = bullish for energy)
 *   Seasonality  — 10-year monthly average return chart
 *   Macro        — DXY + 10Y yield (gold/silver only)
 *   Calendar     — EIA reports, FOMC, OPEC+, NFP, CPI auto-computed
 */

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp, TrendingDown, RefreshCw, AlertTriangle, Shield,
  CheckSquare, Square, ChevronDown, ChevronUp, BarChart3, Activity,
  Scale, BookOpen, Target, Zap, Calendar, AlertCircle,
  XCircle, Award, Info, Layers, Globe, FlaskConical,
} from 'lucide-react';
import { API } from '../lib/api';

// ── Journal helpers ───────────────────────────────────────────────────
const JKEY = 'commodity_journal';
const readJ  = () => { try { return JSON.parse(localStorage.getItem(JKEY) || '[]'); } catch { return []; } };
const writeJ = (e) => localStorage.setItem(JKEY, JSON.stringify(e));

const ASSET_ICONS = { XAU: '🥇', XAG: '🥈', WTI: '🛢️', NG: '🔥' };
const ASSET_COLORS = {
  XAU: { accent: '#f2c14e', subtle: 'rgba(242,193,78,0.12)', border: 'rgba(242,193,78,0.35)' },
  XAG: { accent: '#b0b8c1', subtle: 'rgba(176,184,193,0.12)', border: 'rgba(176,184,193,0.35)' },
  WTI: { accent: '#ff8a00', subtle: 'rgba(255,138,0,0.12)', border: 'rgba(255,138,0,0.35)' },
  NG:  { accent: '#35d0e8', subtle: 'rgba(53,208,232,0.12)', border: 'rgba(53,208,232,0.35)' },
};
const ASSET_NAMES = { XAU: 'Gold', XAG: 'Silver', WTI: 'WTI Crude Oil', NG: 'Natural Gas' };
const ASSET_UNITS = { XAU: '/oz', XAG: '/oz', WTI: '/bbl', NG: '/mmBtu' };
const TABS = ['XAU', 'XAG', 'WTI', 'NG'];

// ── Weekly summary ────────────────────────────────────────────────────
function buildWeekly(journal) {
  const cutoff = Date.now() - 7 * 86400_000;
  const r = journal.filter(e => new Date(e.logged_at).getTime() >= cutoff && e.status !== 'OPEN');
  if (!r.length) return null;
  const wins = r.filter(e => e.status === 'WIN');
  const tagMap = {};
  r.filter(e => e.status === 'LOSS' && e.mistake_tag).forEach(e => {
    tagMap[e.mistake_tag] = (tagMap[e.mistake_tag] || 0) + 1;
  });
  const repeated = Object.entries(tagMap).find(([, c]) => c >= 3);
  return {
    total: r.length, wins: wins.length, losses: r.length - wins.length,
    win_rate: Math.round((wins.length / r.length) * 100),
    avg_rr: Math.round((r.reduce((s, e) => s + (e.r_achieved || 0), 0) / r.length) * 100) / 100,
    repeated_mistake: repeated ? { tag: repeated[0], count: repeated[1] } : null,
  };
}

// ── Trend chip ────────────────────────────────────────────────────────
function TrendChip({ trend }) {
  const m = {
    STRONG_BULLISH: ['↑↑ Strong Bull', 'text-positive bg-positive-subtle'],
    BULLISH:        ['↑ Bullish',       'text-positive bg-positive-subtle'],
    NEUTRAL:        ['→ Neutral',        'text-text-secondary bg-surface'],
    BEARISH:        ['↓ Bearish',       'text-negative bg-negative-subtle'],
    STRONG_BEARISH: ['↓↓ Strong Bear', 'text-negative bg-negative-subtle'],
  };
  const [label, cls] = m[trend] || m.NEUTRAL;
  return <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${cls}`}>{label}</span>;
}

// ── Economic Calendar widget ──────────────────────────────────────────
function CalendarWidget({ events }) {
  if (!events?.length) return null;
  const relevant = events.slice(0, 10);
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Calendar size={13} className="text-gold" />
        <span className="text-sm font-semibold text-text-primary">Economic Calendar</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">Next 7 days</span>
      </div>
      <div className="space-y-2">
        {relevant.map((ev, i) => (
          <div key={i} className={`flex items-start gap-3 rounded-lg p-2.5 border ${
            ev.mutes ? 'border-warning/30 bg-warning-subtle/20' : 'border-border/40 bg-surface/40'
          }`}>
            <div className="flex-shrink-0 text-center min-w-[44px]">
              <div className="font-mono text-[9px] text-text-muted">{new Date(ev.date + 'T12:00:00').toLocaleDateString('en', { month: 'short' })}</div>
              <div className="font-mono text-sm font-bold text-text-primary">{new Date(ev.date + 'T12:00:00').getDate()}</div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-semibold text-text-primary">{ev.event}</span>
                {ev.mutes && <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-warning-subtle text-warning">MUTES SIGNAL</span>}
              </div>
              <div className="flex gap-1 mt-0.5 flex-wrap">
                {(ev.affects || []).map(a => (
                  <span key={a} className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-surface text-text-secondary">{a}</span>
                ))}
              </div>
              <div className="text-[10px] text-text-tertiary mt-0.5 leading-snug">{ev.note}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Seasonality chart (12-bar SVG) ────────────────────────────────────
const MONTH_ABBR = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function SeasonalityChart({ seasonality, symbol }) {
  if (!seasonality?.available) {
    return (
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 size={12} className="text-text-tertiary" />
          <span className="text-sm font-semibold text-text-primary">Seasonality</span>
        </div>
        <p className="text-[11px] text-text-tertiary">{seasonality?.error || 'Data loading…'}</p>
      </div>
    );
  }
  const monthly = seasonality.monthly_avg || {};
  const vals = Array.from({length: 12}, (_, i) => (monthly[i + 1] || 0) * 100);
  const maxAbs = Math.max(...vals.map(Math.abs), 0.1);
  const curMo = (seasonality.current_month || 1) - 1;

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BarChart3 size={12} className="text-purple" />
          <span className="text-sm font-semibold text-text-primary">Seasonality (10Y avg)</span>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
          seasonality.alignment === 'BULLISH_SEASON' ? 'bg-positive-subtle text-positive'
          : seasonality.alignment === 'BEARISH_SEASON' ? 'bg-negative-subtle text-negative'
          : 'bg-surface text-text-secondary'
        }`}>
          {seasonality.alignment === 'BULLISH_SEASON' ? '✓ Bullish season'
           : seasonality.alignment === 'BEARISH_SEASON' ? '✗ Bearish season'
           : '→ Neutral season'}
        </span>
      </div>

      {/* Bar chart */}
      <div className="flex items-end gap-0.5 h-14 mb-1">
        {vals.map((v, i) => {
          const pct = Math.abs(v) / maxAbs * 100;
          const isCur = i === curMo;
          const isPos = v >= 0;
          return (
            <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
              {isPos && (
                <div
                  className={`w-full rounded-t-sm transition-all ${isCur ? 'opacity-100' : 'opacity-60'}`}
                  style={{
                    height: `${pct * 0.45}%`,
                    background: isCur ? '#34d764' : 'rgba(52,215,100,0.5)',
                    minHeight: 1,
                  }}
                />
              )}
              {!isPos && (
                <div
                  className={`w-full rounded-b-sm transition-all ${isCur ? 'opacity-100' : 'opacity-60'}`}
                  style={{
                    height: `${pct * 0.45}%`,
                    background: isCur ? '#ff5d55' : 'rgba(255,93,85,0.5)',
                    minHeight: 1,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="flex gap-0.5">
        {MONTH_ABBR.map((m, i) => (
          <div key={i} className={`flex-1 text-center text-[7px] font-${i === curMo ? 'black' : 'normal'} ${i === curMo ? 'text-accent' : 'text-text-muted'}`}>
            {m[0]}
          </div>
        ))}
      </div>

      <p className="text-[10px] text-text-tertiary mt-2 leading-relaxed">{seasonality.monthly_avg && (
        `${MONTH_ABBR[curMo]}: ${(seasonality.current_month_avg_pct >= 0 ? '+' : '')}${seasonality.current_month_avg_pct}% avg over 10 years`
      )}</p>
    </div>
  );
}

// ── COT Panel ─────────────────────────────────────────────────────────
function COTPanel({ cot }) {
  if (!cot?.available) {
    return (
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <Layers size={12} className="text-text-tertiary" />
          <span className="text-sm font-semibold text-text-primary">COT Positioning (CFTC)</span>
        </div>
        <p className="text-[11px] text-text-tertiary">{cot?.error || 'Loading CFTC data…'}</p>
        <p className="text-[10px] text-text-muted mt-1">CFTC releases weekly disaggregated COT reports (Tuesday data, Friday release).</p>
      </div>
    );
  }
  const pct = cot.mm_percentile;
  const ext = cot.extreme;
  const dir = cot.extreme_direction;

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers size={12} className="text-purple" />
          <span className="text-sm font-semibold text-text-primary">COT Positioning</span>
          <span className="text-[9px] text-text-muted bg-surface px-2 py-0.5 rounded-full">CFTC weekly</span>
        </div>
        {ext && (
          <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
            dir === 'EXTREME_LONG' ? 'bg-negative-subtle text-negative' : 'bg-positive-subtle text-positive'
          }`}>
            {dir === 'EXTREME_LONG' ? '⚠️ Extreme Long' : '⚠️ Extreme Short'}
          </span>
        )}
      </div>

      {/* Percentile bar */}
      <div>
        <div className="flex justify-between text-[9px] text-text-muted mb-1">
          <span>Extreme Short ↓</span>
          <span className={`font-bold ${ext && dir === 'EXTREME_LONG' ? 'text-negative' : ext ? 'text-positive' : 'text-accent'}`}>
            {pct}th percentile
          </span>
          <span>Extreme Long ↑</span>
        </div>
        <div className="h-3 rounded-full bg-surface overflow-hidden relative">
          <div className="absolute inset-0 flex">
            <div className="w-1/5 bg-positive/20 rounded-l-full" />
            <div className="flex-1" />
            <div className="w-1/5 bg-negative/20 rounded-r-full" />
          </div>
          <div
            className={`absolute top-0 h-full w-2 rounded-full ${ext && dir === 'EXTREME_LONG' ? 'bg-negative' : ext ? 'bg-positive' : 'bg-accent'}`}
            style={{ left: `calc(${pct}% - 4px)`, transition: 'left 0.5s' }}
          />
        </div>
        <div className="flex justify-between text-[8px] text-text-muted mt-0.5">
          <span>0</span><span>20 (contrarian buy)</span><span>80 (contrarian sell)</span><span>100</span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-2">
        {[
          ['MM Net', cot.mm_net?.toLocaleString?.() ?? cot.mm_net, 'text-text-primary'],
          ['MM Long', cot.mm_long?.toLocaleString?.(), 'text-positive'],
          ['MM Short', cot.mm_short?.toLocaleString?.(), 'text-negative'],
        ].map(([l, v, c]) => (
          <div key={l} className="bg-surface/60 rounded-lg p-2 text-center">
            <div className="text-[8px] text-text-muted uppercase">{l}</div>
            <div className={`font-mono text-xs font-bold ${c}`}>{v}</div>
          </div>
        ))}
      </div>

      <div className="flex items-start gap-2 rounded-lg bg-surface/40 border border-border/30 px-3 py-2">
        <Info size={11} className="text-text-tertiary flex-shrink-0 mt-0.5" />
        <div className="text-[10px] text-text-secondary leading-relaxed">
          <span className="font-semibold">{cot.signal?.replace(/_/g, ' ')}</span>
          {cot.wow_large_move && <span className="text-warning ml-2">· WoW shift {cot.wow_change_pct > 0 ? '+' : ''}{cot.wow_change_pct}% — large repositioning</span>}
          {ext && <span className="ml-2">· At {pct}th pctile extremes, smart money historically fades crowded positions.</span>}
        </div>
      </div>

      <div className="text-[9px] text-text-muted">Report date: {cot.report_date}</div>
    </div>
  );
}

// ── Futures Curve Panel ───────────────────────────────────────────────
function CurvePanel({ curve, symbol }) {
  if (!curve || curve.shape === 'UNAVAILABLE') {
    return (
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <Activity size={12} className="text-text-tertiary" />
          <span className="text-sm font-semibold text-text-primary">Futures Curve</span>
        </div>
        <p className="text-[11px] text-text-tertiary">Deferred contract data unavailable from market feed.</p>
      </div>
    );
  }
  const isBt = curve.shape === 'BACKWARDATION';
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity size={12} className="text-accent" />
          <span className="text-sm font-semibold text-text-primary">Futures Curve</span>
        </div>
        <span className={`text-[10px] font-bold px-2.5 py-1 rounded-lg ${
          isBt ? 'bg-positive-subtle text-positive' : 'bg-surface text-text-secondary'
        }`}>
          {isBt ? '↑ Backwardation' : '↓ Contango'}
        </span>
      </div>

      <div className="flex items-center gap-4 mb-3">
        <div className="text-center">
          <div className="text-[9px] text-text-muted">Front month</div>
          <div className="font-mono text-base font-bold text-text-primary">${Number(curve.front_price).toLocaleString()}</div>
        </div>
        <div className={`text-lg font-bold ${isBt ? 'text-positive' : 'text-text-muted'}`}>
          {isBt ? '>' : '<'}
        </div>
        <div className="text-center">
          <div className="text-[9px] text-text-muted">{curve.deferred_ticker}</div>
          <div className="font-mono text-base font-bold text-text-primary">${Number(curve.deferred_price).toLocaleString()}</div>
        </div>
        <div className={`font-mono text-sm font-bold ml-auto ${isBt ? 'text-positive' : 'text-text-secondary'}`}>
          {curve.spread_pct > 0 ? '+' : ''}{curve.spread_pct}%
        </div>
      </div>

      <div className="rounded-lg bg-surface/40 border border-border/30 px-3 py-2">
        <p className="text-[11px] text-text-secondary leading-relaxed">{curve.note}</p>
        {symbol === 'WTI' && isBt && (
          <p className="text-[10px] text-positive mt-1 font-semibold">
            For WTI: strengthening backwardation = tightening physical market — high-weight bullish factor.
          </p>
        )}
      </div>
    </div>
  );
}

// ── Macro Panel (Gold/Silver) ─────────────────────────────────────────
function MacroPanel({ macro, symbol }) {
  if (!macro?.available) return null;
  const bullish = macro.gold_silver_confluence === 'BULLISH';
  const bearish = macro.gold_silver_confluence === 'BEARISH';
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Globe size={12} className="text-gold" />
        <span className="text-sm font-semibold text-text-primary">Macro Drivers</span>
        <span className="text-[9px] text-text-muted">(DXY + 10Y yield)</span>
        <span className={`ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full ${
          bullish ? 'bg-positive-subtle text-positive'
          : bearish ? 'bg-negative-subtle text-negative'
          : 'bg-surface text-text-secondary'
        }`}>
          {bullish ? '✓ Macro tailwind' : bearish ? '✗ Macro headwind' : '→ Mixed'}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-surface/60 rounded-xl border border-border/40 p-3">
          <div className="text-[9px] text-text-muted mb-1">DXY (US Dollar Index)</div>
          <div className="font-mono text-xl font-black text-text-primary">{macro.dxy}</div>
          <div className={`text-[10px] font-bold mt-1 ${macro.dxy_trend === 'FALLING' ? 'text-positive' : macro.dxy_trend === 'RISING' ? 'text-negative' : 'text-text-secondary'}`}>
            {macro.dxy_trend} {macro.dxy_10d_change_pct !== null ? `(${macro.dxy_10d_change_pct > 0 ? '+' : ''}${macro.dxy_10d_change_pct}% / 10d)` : ''}
          </div>
          <p className="text-[10px] text-text-muted mt-1">DXY falling → gold/silver tailwind (inverse correlation)</p>
        </div>
        <div className="bg-surface/60 rounded-xl border border-border/40 p-3">
          <div className="text-[9px] text-text-muted mb-1">10-Year Treasury Yield</div>
          <div className="font-mono text-xl font-black text-text-primary">{macro.yield_10y}%</div>
          <div className={`text-[10px] font-bold mt-1 ${macro.yield_trend === 'FALLING' ? 'text-positive' : macro.yield_trend === 'RISING' ? 'text-negative' : 'text-text-secondary'}`}>
            {macro.yield_trend} {macro.yield_10d_change_bp !== null ? `(${macro.yield_10d_change_bp > 0 ? '+' : ''}${macro.yield_10d_change_bp}bp / 10d)` : ''}
          </div>
          <p className="text-[10px] text-text-muted mt-1">Rising real yields = opportunity cost headwind for gold</p>
        </div>
      </div>
      <div className="mt-2 text-[10px] text-text-tertiary">{macro.note}</div>
    </div>
  );
}

// ── Signal Trade Card ─────────────────────────────────────────────────
const COMMODITY_CHECKLIST = [
  { key: 'fund_tech', label: 'Confirmed: this is a fundamental + technical confluence, not technicals alone' },
  { key: 'rr',        label: 'Risk:Reward ≥ 1:2 confirmed. Checked whether asymmetric 1:3+ target is achievable.' },
  { key: 'size',      label: 'Position sized via 1-2% rule, not conviction level or trade "story" size' },
  { key: 'cot',       label: 'Checked COT positioning — not blindly fading an extreme without other confirmation' },
  { key: 'event',     label: 'No entry within 24h of OPEC+/FOMC or immediately after a major geopolitical headline' },
  { key: 'narrative', label: 'If narrative-driven (geopolitical): sized smaller than a pure fundamental setup' },
  { key: 'emotion',   label: '"Am I trading the system, or reacting to a headline?" — confirmed: the system.' },
];

function SignalTradeCard({ signal, symbol, onLog }) {
  const [showChecklist, setShowChecklist] = useState(false);
  const [checks, setChecks] = useState(() => Object.fromEntries(COMMODITY_CHECKLIST.map(c => [c.key, false])));
  const allChecked = Object.values(checks).every(Boolean);
  if (!signal) return null;

  const isLong = signal.direction === 'LONG';
  const col = ASSET_COLORS[symbol] || ASSET_COLORS.XAU;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border-2 overflow-hidden"
      style={{ borderColor: isLong ? 'rgba(52,215,100,0.4)' : 'rgba(255,93,85,0.4)',
               background: `linear-gradient(135deg, ${col.subtle}, transparent)` }}
    >
      {/* Header */}
      <div className={`flex items-center gap-2 px-4 py-2.5 border-b ${isLong ? 'border-positive/20 bg-positive-subtle/15' : 'border-negative/20 bg-negative-subtle/15'}`}>
        {isLong ? <TrendingUp size={14} className="text-positive" /> : <TrendingDown size={14} className="text-negative" />}
        <span className={`text-[12px] font-black uppercase tracking-widest ${isLong ? 'text-positive' : 'text-negative'}`}>
          {signal.direction} — {ASSET_NAMES[symbol]}
        </span>
        {signal.asymmetric_setup && (
          <span className="ml-2 text-[9px] font-black px-2 py-0.5 rounded-full bg-gold-subtle text-gold border border-gold/30">
            ⚡ ASYMMETRIC 1:{signal.risk_reward_2}
          </span>
        )}
        <span className="ml-auto text-[9px] text-text-muted">{signal.timeframe}</span>
      </div>

      <div className="p-4 space-y-4">
        {/* Price levels */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {[
            ['Asset', symbol, 'text-text-primary'],
            ['Direction', signal.direction, isLong ? 'text-positive' : 'text-negative'],
            ['Entry', `$${Number(signal.entry).toLocaleString()}`, 'text-text-primary'],
            ['Stop Loss', `$${Number(signal.stop_loss).toLocaleString()}`, 'text-negative'],
            ['TP1 (1:2)', `$${Number(signal.take_profit_1).toLocaleString()}`, 'text-positive'],
            ['TP2 (1:3)', `$${Number(signal.take_profit_2).toLocaleString()}`, 'text-positive'],
          ].map(([l, v, c]) => (
            <div key={l} className="rounded-xl bg-surface/60 border border-border/40 p-2.5 text-center">
              <div className="text-[8px] text-text-muted uppercase tracking-wider mb-1">{l}</div>
              <div className={`font-mono text-xs font-bold ${c}`}>{v}</div>
            </div>
          ))}
        </div>

        {/* Stop calc + R:R + size */}
        <div className="flex flex-wrap items-center gap-2">
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
                {signal.position_size.units} units · ${signal.position_size.risk_amount} risk
              </span>
            </div>
          )}
        </div>

        {/* SL calc */}
        <div className="text-[10px] text-text-muted font-mono bg-surface/40 rounded-lg px-3 py-1.5">
          Stop calculation: {signal.stop_loss_calc}
        </div>

        {/* 4 meta fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div className="rounded-lg border border-border/40 bg-surface/40 p-2.5">
            <div className="text-[9px] text-text-muted uppercase mb-0.5">Seasonality Alignment</div>
            <div className={`text-[11px] font-semibold ${
              signal.seasonality_alignment?.startsWith('✓') ? 'text-positive'
              : signal.seasonality_alignment?.startsWith('✗') ? 'text-negative'
              : 'text-text-secondary'}`}>
              {signal.seasonality_alignment}
            </div>
          </div>
          <div className="rounded-lg border border-border/40 bg-surface/40 p-2.5">
            <div className="text-[9px] text-text-muted uppercase mb-0.5">COT Summary</div>
            <div className="text-[11px] text-text-secondary">{signal.cot_summary}</div>
          </div>
        </div>

        {/* Event risk */}
        {signal.event_risk_48h?.length > 0 && (
          <div className="flex items-start gap-2 rounded-xl bg-warning-subtle border border-warning/30 px-3 py-2">
            <AlertTriangle size={12} className="text-warning flex-shrink-0 mt-0.5" />
            <div className="text-[10px] text-warning">
              <span className="font-bold">Event risk in 48h: </span>
              {signal.event_risk_48h.map(e => e.event).join(' · ')}. Consider waiting or sizing smaller.
            </div>
          </div>
        )}

        {/* Confidence */}
        <div className="flex items-start gap-2 rounded-xl bg-surface/40 border border-border/30 px-3 py-2">
          <Info size={11} className="text-accent flex-shrink-0 mt-0.5" />
          <span className="text-[11px] text-text-secondary">{signal.confidence_note}</span>
        </div>

        {/* Reasons */}
        <div className="rounded-xl bg-surface/50 border border-border/30 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <BookOpen size={11} className="text-accent" />
            <span className="text-[9px] font-bold uppercase tracking-wider text-text-secondary">Why this signal fired ({signal.confluence_score})</span>
          </div>
          <div className="mb-2">
            {signal.confluence_breakdown?.fundamental?.length > 0 && (
              <>
                <div className="text-[8px] font-bold uppercase text-gold mb-1">Fundamental</div>
                {signal.confluence_breakdown.fundamental.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px] text-text-secondary mb-1">
                    <span className="w-1 h-1 rounded-full bg-gold flex-shrink-0 mt-1.5" />
                    {r}
                  </div>
                ))}
              </>
            )}
            {signal.confluence_breakdown?.technical?.length > 0 && (
              <>
                <div className="text-[8px] font-bold uppercase text-accent mt-1.5 mb-1">Technical</div>
                {signal.confluence_breakdown.technical.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-[11px] text-text-secondary mb-1">
                    <span className="w-1 h-1 rounded-full bg-accent flex-shrink-0 mt-1.5" />
                    {r}
                  </div>
                ))}
              </>
            )}
          </div>
        </div>

        {/* Mindset checklist */}
        <div>
          <button
            onClick={() => setShowChecklist(s => !s)}
            className="w-full flex items-center gap-2 rounded-xl border border-gold/30 bg-gold-subtle/20 px-4 py-2.5 text-left cursor-pointer hover:bg-gold-subtle/30 transition-colors"
          >
            <CheckSquare size={13} className="text-gold" />
            <span className="text-[11px] font-bold text-gold">Commodity Trader Mindset Checklist</span>
            <span className="text-[9px] text-text-muted ml-1">— 7 items (Andurand · Dennis · Dalio · Arnold)</span>
            <span className="ml-auto text-text-secondary">{showChecklist ? <ChevronUp size={13} /> : <ChevronDown size={13} />}</span>
          </button>
          <AnimatePresence>
            {showChecklist && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <div className="mt-2 space-y-2 p-3 rounded-xl bg-surface/40 border border-border/30">
                  {COMMODITY_CHECKLIST.map(({ key, label }) => (
                    <button key={key} onClick={() => setChecks(c => ({ ...c, [key]: !c[key] }))} className="w-full flex items-start gap-2.5 text-left cursor-pointer group">
                      {checks[key]
                        ? <CheckSquare size={13} className="text-positive flex-shrink-0 mt-0.5" />
                        : <Square size={13} className="text-text-tertiary flex-shrink-0 mt-0.5 group-hover:text-text-secondary" />}
                      <span className={`text-[11px] leading-relaxed ${checks[key] ? 'text-text-secondary line-through' : 'text-text-primary'}`}>{label}</span>
                    </button>
                  ))}
                  <motion.button
                    whileTap={{ scale: 0.96 }}
                    onClick={() => allChecked && onLog(signal)}
                    disabled={!allChecked}
                    className={`w-full mt-2 py-2.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
                      allChecked ? 'btn-gradient text-white' : 'bg-surface-hover text-text-muted opacity-50 cursor-not-allowed'
                    }`}
                  >
                    {allChecked ? '✓ All 7 checks passed — Log Trade to Journal' : `Complete checklist (${Object.values(checks).filter(Boolean).length}/7)`}
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

// ── Indicators Panel ──────────────────────────────────────────────────
function IndicatorsPanel({ ind, trend_1h }) {
  if (!ind) return null;
  const { ema: e, rsi, macd, bollinger, vwap_24h, volume_ratio, volume_spike, atr, fibonacci } = ind;
  return (
    <div className="space-y-3">
      <div className="glass-card p-3">
        <div className="flex items-center gap-2 mb-2">
          <Activity size={12} className="text-accent" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">EMA Stack</span>
          <TrendChip trend={trend_1h} />
        </div>
        <div className="flex flex-wrap gap-2">
          {[['EMA 9', e.e9], ['EMA 21', e.e21], ['EMA 50', e.e50], ['EMA 200', e.e200]].filter(([, v]) => v).map(([l, v]) => (
            <div key={l} className="flex items-center gap-1.5 bg-surface px-2.5 py-1 rounded-lg">
              <span className="text-[9px] text-text-muted">{l}</span>
              <span className="font-mono text-[10px] font-bold text-text-primary">${Number(v).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="glass-card p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase text-text-secondary">RSI (14)</span>
            <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${rsi.value >= 70 ? 'bg-negative-subtle text-negative' : rsi.value <= 30 ? 'bg-positive-subtle text-positive' : 'bg-surface text-text-secondary'}`}>
              {rsi.value >= 70 ? 'Overbought' : rsi.value <= 30 ? 'Oversold' : 'Neutral'}
            </span>
          </div>
          <div className="font-mono text-2xl font-black text-text-primary">{rsi.value}</div>
          {rsi.divergence !== 'NONE' && (
            <div className={`text-[9px] font-bold mt-1 ${rsi.divergence.startsWith('BULL') ? 'text-positive' : 'text-negative'}`}>
              {rsi.divergence === 'BULLISH_DIVERGENCE' ? '↗ Bull divergence' : '↘ Bear divergence'}
            </div>
          )}
          <div className="mt-2 h-1.5 rounded-full bg-surface overflow-hidden">
            <div className={`h-full rounded-full ${rsi.value >= 70 ? 'bg-negative' : rsi.value <= 30 ? 'bg-positive' : 'bg-accent'}`} style={{ width: `${rsi.value}%` }} />
          </div>
        </div>
        <div className="glass-card p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase text-text-secondary">MACD</span>
            {macd.cross !== 'NONE' && <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${macd.cross === 'BULLISH_CROSS' ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}`}>{macd.cross === 'BULLISH_CROSS' ? '⚡ Bull cross' : '⚡ Bear cross'}</span>}
          </div>
          <div className={`font-mono text-xl font-black ${macd.bullish ? 'text-positive' : 'text-negative'}`}>{macd.histogram > 0 ? '+' : ''}{macd.histogram}</div>
          <div className="text-[10px] text-text-tertiary mt-1">Line {macd.line} · Signal {macd.signal_line}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="glass-card p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase text-text-secondary">Bollinger Bands</span>
            {bollinger.squeeze && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-warning-subtle text-warning">🔥 SQUEEZE</span>}
          </div>
          <div className="space-y-0.5 text-[11px]">
            {[['Upper', bollinger.upper, 'text-negative'], ['Middle', bollinger.middle, 'text-text-primary'], ['Lower', bollinger.lower, 'text-positive']].map(([l, v, c]) => (
              <div key={l} className="flex justify-between"><span className="text-text-muted">{l}</span><span className={`font-mono ${c}`}>${Number(v).toLocaleString()}</span></div>
            ))}
          </div>
        </div>
        <div className="glass-card p-3">
          <div className="text-[10px] font-bold uppercase text-text-secondary mb-2">VWAP + Volume + ATR</div>
          <div className="space-y-1.5 text-[11px]">
            {vwap_24h && <div className="flex justify-between"><span className="text-text-muted">24H VWAP</span><span className="font-mono text-text-primary">${Number(vwap_24h).toLocaleString()}</span></div>}
            <div className="flex justify-between"><span className="text-text-muted">Vol ratio</span><span className={`font-mono font-bold ${volume_spike ? 'text-warning' : 'text-text-primary'}`}>{volume_ratio}× {volume_spike ? '⚡' : ''}</span></div>
            <div className="flex justify-between"><span className="text-text-muted">ATR(14)</span><span className="font-mono text-text-secondary">${Number(atr).toLocaleString()}</span></div>
          </div>
        </div>
      </div>

      <div className="glass-card p-3">
        <div className="text-[10px] font-bold uppercase text-text-secondary mb-2">Auto Fibonacci (last 100 bars)</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {Object.entries(fibonacci || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between text-[11px]">
              <span className="text-text-muted">{k.replace('fib_', '').replace('swing_', '')} {k.includes('swing') ? (k.includes('high') ? '(H)' : '(L)') : 'Fib'}</span>
              <span className="font-mono text-text-primary">${Number(v).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Asset Header ──────────────────────────────────────────────────────
function AssetHeader({ asset, symbol }) {
  const col = ASSET_COLORS[symbol];
  if (!asset || asset.error) {
    return (
      <div className="glass-card p-4 flex items-center gap-3">
        <span className="text-3xl">{ASSET_ICONS[symbol]}</span>
        <div>
          <div className="font-bold text-text-primary">{ASSET_NAMES[symbol]}</div>
          <div className="text-xs text-negative">{asset?.error || 'Data unavailable'}</div>
        </div>
      </div>
    );
  }

  const atrMult = asset.atr_mult;
  const hasSig = !!asset.signal;
  const muted = !!asset.signal_muted_by;

  return (
    <div className="glass-card p-4" style={{ borderLeft: `3px solid ${col.accent}` }}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl flex-shrink-0"
            style={{ background: col.subtle }}>
            {ASSET_ICONS[symbol]}
          </div>
          <div>
            <div className="text-xl font-black text-text-primary">{ASSET_NAMES[symbol]}</div>
            <div className="text-[10px] text-text-muted">{ASSET_UNITS[symbol]} · {asset.macro_driver?.replace(/_/g, ' ')}</div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <div className="font-mono text-3xl font-black text-text-primary">
            ${Number(asset.price).toLocaleString()}
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <TrendChip trend={asset.trend_4h} />
            {hasSig && !muted && (
              <span className={`text-[9px] font-black px-2 py-0.5 rounded-full ${asset.signal.direction === 'LONG' ? 'bg-positive text-white' : 'bg-negative text-white'}`}>
                ⚡ {asset.signal.direction} SIGNAL
              </span>
            )}
            {muted && (
              <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-warning-subtle text-warning border border-warning/30">
                ⏸ MUTED — {asset.signal_muted_by.type}
              </span>
            )}
            {atrMult === 2 && (
              <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full bg-negative-subtle text-negative">ATR×2 stops</span>
            )}
          </div>
        </div>
      </div>

      {/* Seasonal note */}
      <div className="mt-3 pt-3 border-t border-border/30 flex items-start gap-2">
        <BarChart3 size={11} className="text-text-muted flex-shrink-0 mt-0.5" />
        <span className="text-[10px] text-text-tertiary leading-relaxed">{asset.seasonal_note}</span>
      </div>
    </div>
  );
}

// ── Confluence Panel ──────────────────────────────────────────────────
function ConfluencePanel({ conf, symbol }) {
  if (!conf) return null;
  const { bull_total, bear_total, active_direction } = conf;
  const lead = active_direction || (bull_total > bear_total ? 'bull' : 'bear');
  const techList = active_direction === 'LONG' ? conf.bull_tech : active_direction === 'SHORT' ? conf.bear_tech : conf.bull_tech;
  const fundList = active_direction === 'LONG' ? conf.bull_fund : active_direction === 'SHORT' ? conf.bear_fund : conf.bull_fund;

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Target size={13} className="text-purple" />
        <span className="text-sm font-semibold text-text-primary">Confluence Score</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">9 factors (min 4, ≥1 fundamental)</span>
        <span className={`ml-auto text-[11px] font-black px-2.5 py-1 rounded-lg ${
          active_direction === 'LONG' ? 'bg-positive-subtle text-positive'
          : active_direction === 'SHORT' ? 'bg-negative-subtle text-negative'
          : 'bg-surface text-text-secondary'
        }`}>
          {active_direction ? `${active_direction} — ${bull_total + bear_total}/9` : `No signal — Bull ${bull_total} / Bear ${bear_total}`}
        </span>
      </div>

      {!active_direction && (
        <div className="space-y-2 mb-3">
          {['Bull', 'Bear'].map((dir, idx) => {
            const total = idx === 0 ? bull_total : bear_total;
            return (
              <div key={dir} className="flex items-center gap-3">
                <span className={`text-[10px] font-semibold w-16 ${idx === 0 ? 'text-positive' : 'text-negative'}`}>{dir} {total}/9</span>
                <div className="flex-1 h-2 rounded-full bg-surface overflow-hidden">
                  <div className={`h-full rounded-full ${idx === 0 ? 'bg-positive' : 'bg-negative'}`} style={{ width: `${(total / 9) * 100}%` }} />
                </div>
              </div>
            );
          })}
          <p className="text-[10px] text-text-tertiary">Needs ≥4 total + ≥1 fundamental + 4H/1H agreement. At least one of: COT, seasonality, futures curve, or macro must confirm.</p>
        </div>
      )}

      {active_direction && (
        <div className="space-y-2">
          {fundList?.length > 0 && (
            <div>
              <div className="text-[8px] font-bold uppercase text-gold mb-1">Fundamental ({fundList.length})</div>
              {fundList.map((c, i) => <div key={i} className="flex items-start gap-2 text-[10px] text-text-secondary"><span className="w-1 h-1 rounded-full bg-gold flex-shrink-0 mt-1.5" />{c}</div>)}
            </div>
          )}
          {techList?.length > 0 && (
            <div className="mt-2">
              <div className="text-[8px] font-bold uppercase text-accent mb-1">Technical ({techList.length})</div>
              {techList.map((c, i) => <div key={i} className="flex items-start gap-2 text-[10px] text-text-secondary"><span className="w-1 h-1 rounded-full bg-accent flex-shrink-0 mt-1.5" />{c}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Backtest Panel ────────────────────────────────────────────────────
function BacktestPanel({ symbol }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const run = async () => {
    setRunning(true); setError(null);
    try {
      const r = await fetch(`${API}/api/v1/commodity/backtest?symbol=${symbol}&days=365`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) {
      setError(`Backtest unavailable: ${e.message}`);
    } finally { setRunning(false); }
  };

  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FlaskConical size={13} className="text-purple" />
        <span className="text-sm font-semibold text-text-primary">Technical Backtest</span>
        <span className="text-[10px] text-text-muted bg-surface px-2 py-0.5 rounded-full">1Y, 4H bars</span>
      </div>
      <p className="text-[10px] text-text-secondary">EMA+RSI+MACD signal replayed bar-by-bar. COT/seasonal filters applied live only. Breakdown by season (Winter/Spring/Summer/Autumn).</p>
      <motion.button whileTap={{ scale: 0.96 }} onClick={run} disabled={running}
        className="flex items-center gap-1.5 btn-gradient text-white text-xs font-semibold px-4 py-1.5 rounded-lg cursor-pointer disabled:opacity-50">
        <RefreshCw size={11} className={running ? 'animate-spin' : ''} />
        {running ? 'Running…' : `Run ${symbol} Backtest`}
      </motion.button>
      {error && <div className="flex items-center gap-2 text-[11px] text-warning bg-warning-subtle rounded-lg px-3 py-2"><AlertTriangle size={12} /> {error}</div>}
      {result && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {[
              ['Trades', result.total_trades, 'text-text-primary'],
              ['Win Rate', `${result.win_rate_pct}%`, result.win_rate_pct >= 50 ? 'text-positive' : 'text-warning'],
              ['Avg R', result.avg_r, result.avg_r > 0 ? 'text-positive' : 'text-negative'],
              ['PF', result.profit_factor ?? '—', 'text-text-primary'],
              ['Return', `${result.return_pct}%`, result.return_pct >= 0 ? 'text-positive' : 'text-negative'],
              ['Max DD', `-${result.max_drawdown_pct}%`, 'text-negative'],
            ].map(([l, v, c]) => (
              <div key={l} className="bg-surface/60 rounded-lg p-2 text-center">
                <div className="text-[8px] text-text-muted uppercase">{l}</div>
                <div className={`font-mono text-sm font-bold ${c}`}>{v}</div>
              </div>
            ))}
          </div>
          {result.by_season && (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead><tr className="text-text-muted border-b border-border/40">
                  {['Season','Trades','Win%','Net R'].map(h => <th key={h} className="text-left pb-1 pr-4 text-[9px] uppercase tracking-wider font-medium">{h}</th>)}
                </tr></thead>
                <tbody className="divide-y divide-border/20">
                  {Object.entries(result.by_season).map(([season, b]) => (
                    <tr key={season}>
                      <td className="py-1.5 pr-4 font-semibold text-text-primary">{season}</td>
                      <td className="py-1.5 pr-4 font-mono text-text-secondary">{b.trades}</td>
                      <td className="py-1.5 pr-4 font-mono text-text-secondary">{b.win_rate_pct}%</td>
                      <td className={`py-1.5 font-mono font-bold ${b.net_r >= 0 ? 'text-positive' : 'text-negative'}`}>{b.net_r >= 0 ? '+' : ''}{b.net_r}R</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {result.equity_curve?.length > 1 && (
            <svg viewBox="0 0 400 60" className="w-full h-14" preserveAspectRatio="none">
              <polyline points={result.equity_curve.map((v, i) => {
                const mn = Math.min(...result.equity_curve), mx = Math.max(...result.equity_curve);
                const x = (i / (result.equity_curve.length - 1)) * 400;
                const y = 55 - ((v - mn) / (mx - mn || 1)) * 50;
                return `${x},${y}`;
              }).join(' ')} fill="none" stroke={result.return_pct >= 0 ? '#34d764' : '#ff5d55'} strokeWidth="1.5" />
            </svg>
          )}
          <p className="text-[9px] text-text-muted">{result.note}</p>
        </div>
      )}
    </div>
  );
}

// ── Journal ───────────────────────────────────────────────────────────
const MISTAKE_TAGS = ['Ignored event risk (OPEC/FOMC)', 'COT extreme ignored', 'No fundamental confirmation', 'Counter-trend entry', 'Oversized position', 'Narrative-driven (over-sized)', 'FOMO entry', 'Bad R:R accepted'];

function JournalPanel({ symbol, journal, setJournal }) {
  const [editEntry, setEditEntry] = useState(null);
  const [filter, setFilter] = useState('ALL');
  const entries = journal.filter(e => e.symbol === symbol);
  const filtered = filter === 'ALL' ? entries : entries.filter(e => e.status === filter);

  const updateEntry = (id, updates) => {
    const next = journal.map(e => e.id === id ? { ...e, ...updates } : e);
    writeJ(next); setJournal(next); setEditEntry(null);
  };
  const deleteEntry = (id) => { const next = journal.filter(e => e.id !== id); writeJ(next); setJournal(next); };

  if (!entries.length) return (
    <div className="glass-card p-6 text-center text-text-tertiary">
      <BookOpen size={18} className="mx-auto mb-2" />
      <p className="text-sm">No {symbol} trades logged yet.</p>
      <p className="text-[10px] mt-1">Use the signal card above to log trades.</p>
    </div>
  );

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
              className={`text-[9px] font-bold px-2 py-1 rounded-lg cursor-pointer ${filter === f ? 'badge-gradient text-white' : 'bg-surface text-text-secondary'}`}>{f}</button>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        {filtered.map(e => (
          <div key={e.id} className="flex items-start gap-3 rounded-xl border border-border/40 bg-surface/40 p-3">
            <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-1.5 ${e.status === 'WIN' ? 'bg-positive' : e.status === 'LOSS' ? 'bg-negative' : e.status === 'BREAKEVEN' ? 'bg-accent' : 'bg-warning'}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-[10px] font-bold ${e.direction === 'LONG' ? 'text-positive' : 'text-negative'}`}>{e.direction}</span>
                <span className="font-mono text-[11px] text-text-primary">Entry ${Number(e.entry).toLocaleString()}</span>
                <span className="text-[10px] text-text-muted">SL ${Number(e.sl).toLocaleString()}</span>
                {e.r_achieved != null && <span className={`font-mono text-[10px] font-bold ${e.r_achieved >= 0 ? 'text-positive' : 'text-negative'}`}>{e.r_achieved >= 0 ? '+' : ''}{e.r_achieved?.toFixed(2)}R</span>}
                {e.mistake_tag && <span className="text-[8px] bg-negative-subtle text-negative px-1.5 py-0.5 rounded-full">{e.mistake_tag}</span>}
              </div>
              <div className="text-[9px] text-text-muted mt-0.5">{new Date(e.logged_at).toLocaleDateString()} · {e.confluence_score}</div>
              {e.notes && <div className="text-[10px] text-text-secondary mt-1 italic">"{e.notes}"</div>}
            </div>
            <div className="flex gap-1">
              {e.status === 'OPEN' && <button onClick={() => setEditEntry(e)} className="text-[10px] px-2 py-1 rounded-lg bg-surface-hover text-text-secondary cursor-pointer">Close</button>}
              <button onClick={() => deleteEntry(e.id)} className="p-1 rounded-lg text-text-muted hover:text-negative cursor-pointer"><XCircle size={12} /></button>
            </div>
          </div>
        ))}
      </div>
      {editEntry && (
        <JournalModal
          entry={editEntry}
          tags={MISTAKE_TAGS}
          onClose={() => setEditEntry(null)}
          onSave={u => updateEntry(editEntry.id, u)}
        />
      )}
    </div>
  );
}

function JournalModal({ entry, tags, onClose, onSave }) {
  const [status, setStatus] = useState('WIN');
  const [exitPrice, setExitPrice] = useState('');
  const [mistakeTag, setMistakeTag] = useState('');
  const [notes, setNotes] = useState('');
  const risk = Math.abs((entry?.entry || 0) - (entry?.sl || 0));
  const rAchieved = exitPrice && risk > 0
    ? (entry.direction === 'LONG' ? (parseFloat(exitPrice) - entry.entry) / risk : (entry.entry - parseFloat(exitPrice)) / risk)
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="relative z-10 w-full max-w-md glass-card p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-bold text-text-primary">Close — {entry?.symbol} {entry?.direction}</span>
          <button onClick={onClose} className="text-text-tertiary hover:text-text-secondary cursor-pointer"><XCircle size={18} /></button>
        </div>
        <div className="flex gap-2">
          {['WIN', 'LOSS', 'BREAKEVEN'].map(s => (
            <button key={s} onClick={() => setStatus(s)} className={`flex-1 py-1.5 rounded-lg text-xs font-bold cursor-pointer ${status === s ? (s === 'WIN' ? 'bg-positive text-white' : s === 'LOSS' ? 'bg-negative text-white' : 'bg-accent text-white') : 'bg-surface text-text-secondary'}`}>{s}</button>
          ))}
        </div>
        <div>
          <label className="text-[9px] font-semibold uppercase text-text-muted block mb-1">Exit Price</label>
          <input type="number" value={exitPrice} onChange={e => setExitPrice(e.target.value)}
            className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
            placeholder={`e.g. ${entry?.take_profit_1 || '2400'}`} />
          {rAchieved !== null && <span className={`text-[10px] mt-1 block ${rAchieved >= 0 ? 'text-positive' : 'text-negative'}`}>R: {rAchieved >= 0 ? '+' : ''}{rAchieved.toFixed(2)}R</span>}
        </div>
        {status === 'LOSS' && (
          <div>
            <label className="text-[9px] font-semibold uppercase text-text-muted block mb-1">Mistake Tag</label>
            <select value={mistakeTag} onChange={e => setMistakeTag(e.target.value)} className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-text-primary cursor-pointer">
              <option value="">No specific mistake</option>
              {tags.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        )}
        <div>
          <label className="text-[9px] font-semibold uppercase text-text-muted block mb-1">Notes</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-xs text-text-primary resize-none outline-none focus:border-accent" />
        </div>
        <motion.button whileTap={{ scale: 0.97 }} onClick={() => onSave({ status, exit_price: exitPrice ? parseFloat(exitPrice) : null, mistake_tag: mistakeTag, notes, r_achieved: rAchieved })}
          className="w-full btn-gradient text-white text-sm font-bold py-2.5 rounded-xl cursor-pointer">Save to Journal</motion.button>
      </motion.div>
    </div>
  );
}

// ── Quick Forex-style Signal Card for Commodities ────────────────────
function CommQuickTradeCard({ symbol, signal, price, muted, expanded, onToggle }) {
  const isLong = signal.direction === 'LONG';
  const col = ASSET_COLORS[symbol];
  const fmt = (n) => n != null ? `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 3 })}` : '—';
  const rr1 = signal.risk_reward_1 || '2';
  const rr2 = signal.risk_reward_2 || '3';

  if (muted) return (
    <div className="glass-card p-4 flex items-center gap-3 border border-warning/30 bg-warning-subtle/10">
      <AlertTriangle size={13} className="text-warning flex-shrink-0" />
      <div>
        <div className="text-sm font-semibold text-text-primary">{ASSET_ICONS[symbol]} {ASSET_NAMES[symbol]} — Signal Muted</div>
        <div className="text-[11px] text-warning mt-0.5">Event: {signal.signal_muted_by?.event || 'Scheduled event'} — wait {signal.signal_muted_by?.window_h || '24'}h before entering.</div>
      </div>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card overflow-hidden border transition-all duration-300 cursor-pointer"
      style={{ borderColor: isLong ? 'rgba(63,185,80,0.35)' : 'rgba(248,81,73,0.35)', boxShadow: isLong ? '0 0 20px rgba(63,185,80,0.08)' : '0 0 20px rgba(248,81,73,0.08)' }}
      onClick={onToggle}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          {/* Left: badge + asset */}
          <div className="flex items-center gap-3 min-w-0">
            <div className={`px-3 py-1.5 rounded-lg font-bold text-sm flex-shrink-0 ${isLong ? 'bg-positive text-white' : 'bg-negative text-white'}`}>
              {isLong ? '▲ BUY' : '▼ SELL'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl leading-none">{ASSET_ICONS[symbol]}</span>
                <span className="text-base font-bold font-mono text-text-primary">{ASSET_NAMES[symbol]}</span>
                <span className="text-[9px] font-bold px-2 py-0.5 rounded-full" style={{ background: col.subtle, color: col.accent }}>
                  {symbol} · {ASSET_UNITS[symbol]}
                </span>
                {signal.confluence_score && (
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-purple-subtle/40 text-purple">{signal.confluence_score}</span>
                )}
              </div>
              <div className="text-[10px] text-text-muted mt-0.5">{signal.timeframe || '4H trend / 1H entry'}</div>
            </div>
          </div>
          {/* Right: price + chevron */}
          <div className="text-right flex-shrink-0">
            <div className="font-mono text-lg font-bold text-text-primary">{fmt(price)}</div>
            <div className="text-[9px] text-text-muted">Current</div>
            <ChevronDown size={13} className={`text-text-muted mt-1 ml-auto transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </div>
        </div>

        {/* Entry / SL / TP grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
          {[
            { label: 'ENTRY',            val: fmt(signal.entry),         color: 'text-text-primary' },
            { label: 'STOP LOSS',        val: fmt(signal.stop_loss),     color: 'text-negative'     },
            { label: `TP1 (1:${rr1})`,   val: fmt(signal.take_profit_1), color: 'text-positive'     },
            { label: `TP2 (1:${rr2})`,   val: fmt(signal.take_profit_2), color: 'text-positive'     },
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
            <span>Position: <span className="font-mono font-bold">{signal.position_size?.units?.toFixed(4) || '—'} units</span></span>
            <span>· Risk: <span className="font-mono font-bold text-warning">${signal.position_size?.risk_amount || '—'}</span></span>
          </div>
        )}
      </div>

      {/* Expanded: reasons */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden border-t border-border/30"
          >
            <div className="p-4 bg-surface/30 space-y-2">
              {signal.confidence_note && (
                <div className="flex items-start gap-2 rounded-lg bg-accent-subtle/30 border border-accent/20 px-3 py-2">
                  <Info size={10} className="text-accent flex-shrink-0 mt-0.5" />
                  <span className="text-[11px] text-text-secondary">{signal.confidence_note}</span>
                </div>
              )}
              <div className="text-[9px] font-bold uppercase tracking-wider text-text-muted">Why this signal fired</div>
              <ul className="space-y-1">
                {signal.reasons?.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-text-secondary">
                    <span className={`w-1 h-1 rounded-full flex-shrink-0 mt-1.5 ${isLong ? 'bg-positive' : 'bg-negative'}`} />
                    {r}
                  </li>
                ))}
              </ul>
              {signal.seasonality_tag && (
                <div className="text-[10px] text-text-muted">Seasonality: {signal.seasonality_tag}</div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────
export default function CommodityPage() {
  const [activeTab, setActiveTab] = useState('XAU');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [journal, setJournal] = useState(readJ);
  const [balance, setBalance] = useState(10000);
  const [riskPct, setRiskPct] = useState(1.0);
  const [showRisk, setShowRisk] = useState(false);
  const [geoPolitical, setGeoPolitical] = useState(false);
  const [expandedSig, setExpandedSig] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/commodity/signals?balance=${balance}&risk_pct=${riskPct}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      console.error('Commodity fetch failed:', e);
      setData(null);
    } finally { setLoading(false); }
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
      exit_price: null, r_achieved: null, mistake_tag: null, notes: null,
    };
    const next = [entry, ...journal];
    writeJ(next); setJournal(next);
  };

  const asset = data?.assets?.[activeTab];
  const weekly = buildWeekly(journal);
  const col = ASSET_COLORS[activeTab];

  return (
    <div className="p-4 lg:p-5 min-h-screen max-w-[1200px] mx-auto space-y-4">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gold-subtle flex items-center justify-center">
              <Layers size={16} className="text-gold" />
            </div>
            <h1 className="text-xl font-bold text-text-primary">Commodity Analysis</h1>
            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-gold-subtle text-gold">XAU · XAG · WTI · NG</span>
          </div>
          <p className="text-xs text-text-secondary mt-1 max-w-[680px] leading-relaxed">
            9-factor confluence analysis — 6 technical + 3 fundamental (COT, seasonality, futures curve / macro).
            Minimum 4 confluences required; at least 1 must be fundamental. Signals muted around FOMC/OPEC+/EIA events.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowRisk(s => !s)}
            className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary bg-surface border border-border rounded-lg px-3 py-2 cursor-pointer">
            <Shield size={12} /> Risk
          </button>
          <motion.button whileTap={{ scale: 0.95 }} onClick={load}
            className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary bg-surface border border-border rounded-lg px-3 py-2 cursor-pointer">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </motion.button>
        </div>
      </motion.div>

      {/* Geopolitical toggle */}
      {geoPolitical && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex items-center gap-3 rounded-xl border border-warning/40 bg-warning-subtle/30 px-4 py-3">
          <AlertCircle size={14} className="text-warning flex-shrink-0" />
          <div className="flex-1">
            <span className="text-xs font-bold text-warning">Geopolitical Elevated Volatility Mode Active</span>
            <span className="text-[10px] text-warning/80 ml-2">— Size all positions 30–50% smaller than normal. Let initial spike settle before entering.</span>
          </div>
          <button onClick={() => setGeoPolitical(false)} className="text-warning/60 hover:text-warning cursor-pointer"><XCircle size={14} /></button>
        </motion.div>
      )}
      {!geoPolitical && (
        <button onClick={() => setGeoPolitical(true)}
          className="text-[10px] text-text-muted hover:text-warning flex items-center gap-1.5 cursor-pointer transition-colors">
          <AlertCircle size={11} /> Flag active geopolitical event (conflict, sanctions, supply disruption)
        </button>
      )}

      {/* Risk settings */}
      <AnimatePresence>
        {showRisk && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="glass-card p-4 flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-3">
                <label className="text-[10px] font-semibold uppercase text-text-muted">Account Balance</label>
                <input type="number" value={balance} onChange={e => setBalance(parseFloat(e.target.value) || 10000)}
                  className="bg-surface border border-border rounded-lg px-3 py-1.5 text-sm font-mono text-text-primary w-28 outline-none focus:border-accent" />
              </div>
              <div className="flex items-center gap-3">
                <label className="text-[10px] font-semibold uppercase text-text-muted">Risk %</label>
                <div className="flex gap-1">
                  {[0.5, 1.0, 1.5, 2.0].map(r => (
                    <button key={r} onClick={() => setRiskPct(r)}
                      className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer ${riskPct === r ? 'btn-gradient text-white' : 'bg-surface text-text-secondary hover:text-text-primary'}`}>{r}%</button>
                  ))}
                </div>
              </div>
              <p className="text-[10px] text-text-muted">Max 2 concurrent commodity positions · Natural Gas: ATR×2 stops (wider for NG's volatility) · Daily circuit breaker: 3% loss</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Active Trade Signals (Forex-style cards) ── */}
      {data && (() => {
        const allSyms = ['XAU', 'XAG', 'WTI', 'NG'];
        const activeSigs = allSyms.filter(s => data.assets?.[s]?.signal);
        const mutedSigs  = allSyms.filter(s => !data.assets?.[s]?.signal && data.assets?.[s]?.signal_muted_by);
        return (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Zap size={13} className="text-gold" />
              <span className="text-sm font-semibold text-text-primary">Active Trade Signals</span>
              <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${activeSigs.length > 0 ? 'bg-positive-subtle text-positive' : 'bg-surface text-text-muted'}`}>
                {activeSigs.length} / 4 assets
              </span>
              <span className="text-[9px] text-text-muted ml-auto">{data.generated_at?.split('T')[1]?.slice(0, 8)} UTC</span>
            </div>
            {activeSigs.length > 0 ? (
              <div className="space-y-3">
                {activeSigs.map(sym => (
                  <CommQuickTradeCard
                    key={sym}
                    symbol={sym}
                    signal={data.assets[sym].signal}
                    price={data.assets[sym].price}
                    muted={false}
                    expanded={expandedSig === sym}
                    onToggle={() => setExpandedSig(p => p === sym ? null : sym)}
                  />
                ))}
                {mutedSigs.map(sym => (
                  <CommQuickTradeCard
                    key={sym + '-muted'}
                    symbol={sym}
                    signal={{ ...data.assets[sym], signal_muted_by: data.assets[sym].signal_muted_by }}
                    price={data.assets[sym].price}
                    muted={true}
                    expanded={false}
                    onToggle={() => {}}
                  />
                ))}
              </div>
            ) : (
              <div className="glass-card p-6 flex items-center gap-3 text-text-secondary">
                <Target size={16} className="text-text-muted" />
                <div>
                  <div className="text-sm font-semibold text-text-primary">No commodity trade setups right now</div>
                  <div className="text-[11px] text-text-tertiary mt-0.5">
                    Need ≥4 confluences + ≥1 fundamental (COT/seasonality/curve/macro) + 4H & 1H trend agreement.
                    {mutedSigs.length > 0 && ` ${mutedSigs.join(', ')} muted for scheduled events.`}
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* Layout: tabs + calendar side by side on large screens */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-4">

        {/* Left: asset analysis */}
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex gap-1 p-1 rounded-xl bg-surface/60 border border-border/40">
            {TABS.map(sym => {
              const hasSig = data?.assets?.[sym]?.signal && !data?.assets?.[sym]?.signal_muted_by;
              return (
                <button key={sym} onClick={() => setActiveTab(sym)}
                  className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all cursor-pointer relative ${activeTab === sym ? 'text-white shadow-md' : 'text-text-secondary hover:text-text-primary'}`}
                  style={{ background: activeTab === sym ? `linear-gradient(135deg, ${ASSET_COLORS[sym].accent}99, ${ASSET_COLORS[sym].accent}55)` : undefined }}>
                  {ASSET_ICONS[sym]} {sym}
                  {hasSig && <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-positive" />}
                </button>
              );
            })}
          </div>

          {loading ? (
            <div className="glass-card p-12 flex items-center justify-center gap-2 text-text-tertiary">
              <RefreshCw size={15} className="animate-spin" />
              Fetching {ASSET_NAMES[activeTab]} data — OHLCV + COT + seasonality + macro…
            </div>
          ) : !data ? (
            <div className="glass-card p-8 text-center">
              <AlertTriangle size={20} className="mx-auto text-warning mb-2" />
              <p className="text-sm text-text-secondary">Backend is starting up — refresh in a few seconds.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <AssetHeader asset={asset} symbol={activeTab} />

              {/* Muted signal notice */}
              {asset?.signal_muted_by && (
                <div className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning-subtle/20 px-4 py-3">
                  <AlertTriangle size={13} className="text-warning flex-shrink-0 mt-0.5" />
                  <div className="text-[11px] text-warning">
                    <span className="font-bold">Signal muted: </span>
                    {asset.signal_muted_by.event} on {asset.signal_muted_by.date}.
                    Wait {asset.signal_muted_by.window_h}h around this event before entering.
                    {asset.signal && <span className="text-warning/70"> (A technical signal was present but suppressed.)</span>}
                  </div>
                </div>
              )}

              <ConfluencePanel conf={asset?.confluence} symbol={activeTab} />

              {asset?.signal ? (
                <SignalTradeCard signal={asset.signal} symbol={activeTab} onLog={sig => logTrade(sig, activeTab)} />
              ) : (
                <div className="glass-card p-6 flex items-center gap-3 text-text-secondary">
                  <Target size={15} />
                  <div>
                    <div className="text-sm font-semibold text-text-primary">No signal for {ASSET_NAMES[activeTab]}</div>
                    <div className="text-[11px] text-text-tertiary mt-0.5">
                      {asset?.confluence
                        ? `Bull ${asset.confluence.bull_total}/9, Bear ${asset.confluence.bear_total}/9 — need ≥4 total + ≥1 fundamental. `
                        : ''}
                      {asset?.signal_muted_by ? 'Event mute active.' : 'Wait for stronger alignment.'}
                    </div>
                  </div>
                </div>
              )}

              {/* Fundamental panels */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <COTPanel cot={asset?.fundamentals?.cot} />
                <CurvePanel curve={asset?.fundamentals?.curve} symbol={activeTab} />
              </div>

              <SeasonalityChart seasonality={asset?.fundamentals?.seasonality} symbol={activeTab} />
              {(activeTab === 'XAU' || activeTab === 'XAG') && <MacroPanel macro={asset?.fundamentals?.macro} symbol={activeTab} />}

              <IndicatorsPanel ind={asset?.indicators} trend_1h={asset?.trend_1h} />
              <BacktestPanel symbol={activeTab} />

              {weekly && (
                <div className="glass-card p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Award size={13} className="text-gold" />
                    <span className="text-sm font-semibold text-text-primary">Weekly Summary — All Commodities</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 mb-3">
                    {[['Trades', weekly.total, 'text-text-primary'], ['Win Rate', `${weekly.win_rate}%`, weekly.win_rate >= 55 ? 'text-positive' : 'text-warning'], ['Wins', weekly.wins, 'text-positive'], ['Avg R', `${weekly.avg_rr >= 0 ? '+' : ''}${weekly.avg_rr}R`, weekly.avg_rr >= 0 ? 'text-positive' : 'text-negative']].map(([l, v, c]) => (
                      <div key={l} className="bg-surface/60 rounded-xl p-2.5 text-center">
                        <div className="text-[9px] text-text-muted uppercase">{l}</div>
                        <div className={`font-mono text-sm font-bold ${c}`}>{v}</div>
                      </div>
                    ))}
                  </div>
                  {weekly.repeated_mistake && (
                    <div className="flex items-start gap-2 rounded-xl bg-warning-subtle border border-warning/30 px-3 py-2">
                      <AlertCircle size={12} className="text-warning flex-shrink-0 mt-0.5" />
                      <span className="text-[11px] text-warning">⚠️ Repeated mistake: "<strong>{weekly.repeated_mistake.tag}</strong>" — {weekly.repeated_mistake.count}× this week. Review before next trade.</span>
                    </div>
                  )}
                </div>
              )}

              <JournalPanel symbol={activeTab} journal={journal} setJournal={setJournal} />
            </div>
          )}
        </div>

        {/* Right: economic calendar (sticky on large screens) */}
        <div className="space-y-4">
          <CalendarWidget events={data?.calendar} />

          {/* Trader philosophy */}
          <div className="glass-card p-4">
            <div className="text-[10px] font-bold uppercase tracking-wider text-gold mb-3">Commodity Trader Wisdom</div>
            <div className="space-y-2.5">
              {[
                ['Pierre Andurand', 'Oil moves on the delta vs expectations, not the absolute level. Fundamentals always win over paper markets — eventually.'],
                ['John Arnold', 'The difference between a trade and a story is the stop loss. Everything else is just narrative.'],
                ['Richard Dennis', 'Ride winners, cut losers. The market tells you when you\'re wrong — listen to it.'],
                ['Ray Dalio', 'Diversify across uncorrelated assets. Gold and oil are not the same bet.'],
              ].map(([name, quote]) => (
                <div key={name} className="rounded-lg bg-surface/40 border border-border/30 p-2.5">
                  <div className="text-[9px] font-bold text-gold mb-1">{name}</div>
                  <div className="text-[10px] text-text-secondary italic leading-relaxed">"{quote}"</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-2 rounded-xl border border-border/60 bg-surface/40 px-4 py-3">
        <AlertTriangle size={13} className="text-warning flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-text-secondary leading-relaxed">
          <strong className="text-text-primary">Commodity signals are analytical and educational tools only — not financial advice.</strong>{' '}
          Commodity markets carry substantial risk of loss due to leverage and geopolitical volatility.
          COT, seasonal, and macro data are educational references. Historical trader strategies referenced
          here do not guarantee future results. Always consult a licensed financial adviser before trading.
        </p>
      </div>
    </div>
  );
}
