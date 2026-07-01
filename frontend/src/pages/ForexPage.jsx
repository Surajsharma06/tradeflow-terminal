/**
 * Forex Intelligence Page — Smart Money Concepts (ICT) + Live Chart
 * ==================================================================
 * Tabs:
 *   1. SMC Signals — existing FVG + Liquidity Sweep signals
 *   2. Live Chart  — candlestick chart + Entry/SL/TP lines for any pair
 *   3. HTF Bias    — higher timeframe EMA bias table
 *
 * All forex pairs supported. Chart uses lightweight-charts v5.
 * Auto-refresh every 2 minutes (signals) and 60 seconds (chart).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Globe, RefreshCw, Shield, Zap, TrendingUp, TrendingDown,
  AlertTriangle, Clock, Target, ChevronRight, Wifi, WifiOff,
  Activity, BarChart3, Minus, CheckCircle, XCircle, Info,
  BarChart2, BookOpen, PlusCircle, Trash2, Layers,
} from 'lucide-react';
import ForexChart from '../components/ForexChart';
import OrderBook from '../components/OrderBook';
import { API } from '../lib/api';

const REFRESH_INTERVAL = 2 * 60 * 1000; // 2 min for signals
const CHART_REFRESH    = 60 * 1000;     // 60 sec for chart

// ── Demo fallback signals ──────────────────────────────────────────────────
const DEMO_SIGNALS = [
  {
    pair: 'AUD/USD', direction: 'BUY', entry: 0.64812, stop_loss: 0.64510,
    tp1: 0.65114, tp2: 0.65416, tp3: 0.65718, pips_risk: 30.2,
    confidence: 88, ema9: 0.64820, ema15: 0.64780, ema200: 0.64200,
    current_price: 0.64812, htf_bias: 'bullish',
    ema_aligned: true, fvg_present: true, liq_sweep: true,
    fvg_zone: [0.64850, 0.64720], sweep_level: 0.64505,
    reason: '4H bias: BULLISH | Sell-side sweep @ 0.64505 | Bullish FVG 0.64720–0.64850',
    timestamp: 'Demo Mode', timeframe_entry: '15m', timeframe_bias: '4H',
  },
  {
    pair: 'EUR/USD', direction: 'SELL', entry: 1.13415, stop_loss: 1.13780,
    tp1: 1.13050, tp2: 1.12685, tp3: 1.12320, pips_risk: 36.5,
    confidence: 82, ema9: 1.13380, ema15: 1.13450, ema200: 1.14200,
    current_price: 1.13415, htf_bias: 'bearish',
    ema_aligned: true, fvg_present: true, liq_sweep: false,
    fvg_zone: [1.13500, 1.13350], sweep_level: null,
    reason: '4H bias: BEARISH | Bearish FVG 1.13350–1.13500 | EMA9 < EMA15',
    timestamp: 'Demo Mode', timeframe_entry: '15m', timeframe_bias: '4H',
  },
  {
    pair: 'GBP/USD', direction: 'BUY', entry: 1.27320, stop_loss: 1.26980,
    tp1: 1.27660, tp2: 1.28000, tp3: 1.28340, pips_risk: 34.0,
    confidence: 74, ema9: 1.27350, ema15: 1.27290, ema200: 1.26800,
    current_price: 1.27320, htf_bias: 'bullish',
    ema_aligned: true, fvg_present: false, liq_sweep: true,
    fvg_zone: null, sweep_level: 1.26975,
    reason: '4H bias: BULLISH | Sell-side sweep @ 1.26975 | EMA9 > EMA15',
    timestamp: 'Demo Mode', timeframe_entry: '15m', timeframe_bias: '4H',
  },
];

// ── Helpers ────────────────────────────────────────────────────────────────
function formatPrice(p, pair) {
  if (!p && p !== 0) return '—';
  if (pair?.includes('JPY') || pair?.includes('INR')) return Number(p).toFixed(3);
  if (pair?.includes('XAU')) return Number(p).toFixed(2);
  if (pair?.includes('BTC') || pair?.includes('ETH')) return Number(p).toFixed(2);
  return Number(p).toFixed(5);
}

function confColor(c) {
  if (c >= 80) return '#3fb950';
  if (c >= 65) return '#e3b341';
  return '#f85149';
}

function biasIcon(bias) {
  if (bias === 'bullish') return { Icon: TrendingUp,   color: '#3fb950', label: '4H BULLISH' };
  if (bias === 'bearish') return { Icon: TrendingDown, color: '#f85149', label: '4H BEARISH' };
  return { Icon: Minus, color: '#8b949e', label: '4H NEUTRAL' };
}

function useNow() {
  const [t, setT] = useState('');
  useEffect(() => {
    const tick = () => setT(new Date().toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
    }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return t;
}

function Countdown({ nextRefresh }) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const tick = () => setSecs(Math.max(0, Math.round((nextRefresh - Date.now()) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [nextRefresh]);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return (
    <span className="font-mono text-[10px] text-text-muted">
      next refresh {m}:{String(s).padStart(2, '0')}
    </span>
  );
}

// ── EMA Levels ─────────────────────────────────────────────────────────────
function EMALevels({ sig }) {
  const price = sig.current_price || sig.entry;
  const levels = [
    { label: 'EMA 9',   val: sig.ema9,   color: '#58a6ff' },
    { label: 'EMA 15',  val: sig.ema15,  color: '#e3b341' },
    { label: 'EMA 200', val: sig.ema200, color: '#bc8cff' },
  ];
  return (
    <div className="grid grid-cols-3 gap-1.5 mt-2">
      {levels.map(({ label, val, color }) => {
        const abv = price > val;
        return (
          <div key={label} className="rounded-lg p-2 text-center" style={{ background: color + '15' }}>
            <div className="text-[9px] font-bold mb-0.5" style={{ color }}>{label}</div>
            <div className="font-mono text-[10px] text-text-primary">{formatPrice(val, sig.pair)}</div>
            <div className="text-[8px] mt-0.5" style={{ color: abv ? '#3fb950' : '#f85149' }}>
              {abv ? 'ABOVE' : 'BELOW'}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Confluence Checklist ───────────────────────────────────────────────────
function ConfluenceList({ sig }) {
  const items = [
    { label: `4H Bias ${sig.htf_bias?.toUpperCase() || '—'}`, ok: sig.htf_bias !== 'neutral', weight: 30 },
    { label: 'Liquidity Sweep', ok: sig.liq_sweep, weight: 35 },
    { label: 'Fair Value Gap', ok: sig.fvg_present, weight: 25 },
    { label: 'EMA 9/15 Aligned', ok: sig.ema_aligned, weight: 10 },
  ];
  return (
    <div className="space-y-1 mt-2">
      {items.map(({ label, ok, weight }) => (
        <div key={label} className="flex items-center gap-2">
          {ok
            ? <CheckCircle size={11} className="text-positive flex-shrink-0" />
            : <XCircle    size={11} className="text-text-muted flex-shrink-0" />}
          <span className={`text-[10px] flex-1 ${ok ? 'text-text-secondary' : 'text-text-muted line-through'}`}>{label}</span>
          <span className={`text-[9px] font-mono ${ok ? 'text-positive' : 'text-text-muted'}`}>+{weight}pts</span>
        </div>
      ))}
    </div>
  );
}

// ── Signal Card ────────────────────────────────────────────────────────────
function SignalCard({ sig, expanded, onToggle, onViewChart }) {
  const isBuy = sig.direction === 'BUY';
  const cc    = confColor(sig.confidence);
  const bias  = biasIcon(sig.htf_bias);

  return (
    <div
      className={`glass-card overflow-hidden transition-all duration-300 border ${
        isBuy ? 'border-positive/30' : 'border-negative/30'
      }`}
      style={{ boxShadow: isBuy ? '0 0 20px rgba(63,185,80,0.08)' : '0 0 20px rgba(248,81,73,0.08)' }}
    >
      <div
        className="p-4 cursor-pointer hover:bg-surface-hover/30 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`px-3 py-1.5 rounded-lg font-bold text-sm flex-shrink-0 ${
              isBuy ? 'bg-positive text-white' : 'bg-negative text-white'
            }`}>
              {isBuy ? '▲ BUY' : '▼ SELL'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold font-mono text-text-primary">{sig.pair}</span>
                <bias.Icon size={12} style={{ color: bias.color }} />
                <span className="text-[9px] font-bold" style={{ color: bias.color }}>{bias.label}</span>
              </div>
              <div className="text-[10px] text-text-muted mt-0.5 flex items-center gap-1">
                <Clock size={8} />
                {sig.timestamp}
              </div>
            </div>
          </div>

          <div className="text-right flex-shrink-0">
            <div className="text-xl font-bold font-mono" style={{ color: cc }}>{sig.confidence}%</div>
            <div className="text-[9px] font-bold tracking-wider" style={{ color: cc }}>CONFIDENCE</div>
            <div className="h-1.5 w-16 bg-surface rounded-full mt-1 ml-auto">
              <div className="h-1.5 rounded-full transition-all" style={{ width: `${sig.confidence}%`, background: cc }} />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
          {[
            { label: 'ENTRY',     val: formatPrice(sig.entry, sig.pair),     color: 'text-text-primary' },
            { label: 'SL',        val: formatPrice(sig.stop_loss, sig.pair), color: 'text-negative'     },
            { label: 'TP3 (1:3)', val: formatPrice(sig.tp3, sig.pair),       color: 'text-positive'     },
            { label: `Risk: ${sig.pips_risk} pips`, val: 'R:R 1:3', color: 'text-accent' },
          ].map(({ label, val, color }) => (
            <div key={label} className="rounded-lg bg-surface/60 p-2 text-center">
              <div className="text-[9px] text-text-muted mb-0.5">{label}</div>
              <div className={`font-mono text-xs font-bold ${color}`}>{val}</div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 mt-2">
          <span className="text-[9px] px-2 py-0.5 rounded-full bg-accent-subtle text-accent font-bold">
            {sig.timeframe_entry || '1h'}
          </span>
          <span className="text-[9px] px-2 py-0.5 rounded-full bg-purple-subtle text-purple font-bold">
            Bias: {sig.timeframe_bias || '4H'}
          </span>
          {sig.sessions && (
            <span className="text-[9px] px-2 py-0.5 rounded-full bg-surface text-text-muted border border-border font-mono">
              {Array.isArray(sig.sessions) ? sig.sessions.join(' + ') : sig.sessions}
            </span>
          )}
          {sig.liq_sweep && (
            <span className="text-[9px] px-2 py-0.5 rounded-full bg-warning-subtle text-warning font-bold">
              Liq. Sweep
            </span>
          )}
          {sig.fvg_present && (
            <span className="text-[9px] px-2 py-0.5 rounded-full bg-info-subtle text-info font-bold">
              FVG
            </span>
          )}
          {/* MTF confluence badge */}
          {sig.mtf_score !== undefined && (
            <span
              className="text-[9px] px-2 py-0.5 rounded-full font-bold"
              style={{
                background: sig.mtf_score >= 2 ? '#3fb95022' : '#f8514922',
                color:      sig.mtf_score >= 2 ? '#3fb950'   : '#f85149',
              }}
              title={sig.mtf_detail ? Object.entries(sig.mtf_detail).map(([k,v]) => `${k}: ${v}`).join(' | ') : ''}
            >
              <Layers size={7} style={{ display:'inline', marginRight:2 }} />
              {sig.mtf_score}/3 TFs
            </span>
          )}
          {/* News warning */}
          {sig.news_warning && (
            <span
              className="text-[9px] px-2 py-0.5 rounded-full bg-red-900/30 text-red-400 font-bold cursor-help"
              title={sig.news_events ? sig.news_events.join('\n') : 'High-impact news nearby'}
            >
              ⚠ News
            </span>
          )}
          {onViewChart && (
            <button
              onClick={(e) => { e.stopPropagation(); onViewChart(sig); }}
              className="ml-auto flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-lg bg-accent-subtle text-accent hover:bg-accent hover:text-white transition-all font-bold"
            >
              <BarChart2 size={8} /> Chart
            </button>
          )}
          <ChevronRight size={12} className={`text-text-muted transition-transform ${expanded ? 'rotate-90' : ''}`} />
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border/30 p-4 space-y-3 bg-surface/30">
          <div>
            <div className="text-[10px] font-bold text-text-secondary uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Info size={9} /> Analysis
            </div>
            <div className="text-[11px] text-text-secondary leading-relaxed">{sig.reason || '—'}</div>
          </div>

          <div>
            <div className="text-[10px] font-bold text-text-secondary uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Target size={9} /> Targets
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: 'TP1 (Conservative)', val: sig.tp1 },
                { label: 'TP2 (Recommended)',  val: sig.tp2 },
                { label: 'TP3 (Aggressive)',   val: sig.tp3 },
              ].map(({ label, val }) => (
                <div key={label} className="rounded-lg bg-positive-subtle/50 p-2 text-center">
                  <div className="text-[8px] text-text-muted mb-0.5">{label}</div>
                  <div className="font-mono text-xs font-bold text-positive">{formatPrice(val, sig.pair)}</div>
                </div>
              ))}
            </div>
          </div>

          {sig.fvg_zone && (
            <div>
              <div className="text-[10px] font-bold text-text-secondary uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <BarChart3 size={9} /> Fair Value Gap Zone
              </div>
              <div className="rounded-lg p-2 bg-info-subtle flex items-center justify-between">
                <span className="text-[10px] text-info">Bottom: {formatPrice(sig.fvg_zone[1], sig.pair)}</span>
                <span className="text-[9px] text-text-muted">↔</span>
                <span className="text-[10px] text-info">Top: {formatPrice(sig.fvg_zone[0], sig.pair)}</span>
              </div>
            </div>
          )}

          {sig.sweep_level && (
            <div className="rounded-lg p-2 bg-warning-subtle flex items-center gap-2">
              <AlertTriangle size={10} className="text-warning flex-shrink-0" />
              <span className="text-[10px] text-warning">
                Liquidity swept at: <span className="font-mono font-bold">{formatPrice(sig.sweep_level, sig.pair)}</span>
              </span>
            </div>
          )}

          {(sig.ema9 || sig.ema15 || sig.ema200) && (
            <div>
              <div className="text-[10px] font-bold text-text-secondary uppercase tracking-wider mb-1 flex items-center gap-1">
                <Activity size={9} /> EMA Levels
              </div>
              <EMALevels sig={sig} />
            </div>
          )}

          {sig.liq_sweep !== undefined && (
            <div>
              <div className="text-[10px] font-bold text-text-secondary uppercase tracking-wider mb-1 flex items-center gap-1">
                <Shield size={9} /> Confluence Score
              </div>
              <ConfluenceList sig={sig} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Pair Selector ──────────────────────────────────────────────────────────
function PairSelector({ value, onChange }) {
  const groups = [
    { label: 'Majors',       pairs: ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD'] },
    { label: 'EUR Crosses',  pairs: ['EUR/GBP', 'EUR/JPY', 'EUR/AUD', 'EUR/CAD', 'EUR/CHF', 'EUR/NZD'] },
    { label: 'GBP Crosses',  pairs: ['GBP/JPY', 'GBP/AUD', 'GBP/CAD', 'GBP/CHF', 'GBP/NZD'] },
    { label: 'Minors',       pairs: ['AUD/CAD', 'AUD/CHF', 'AUD/JPY', 'AUD/NZD', 'CAD/CHF', 'CAD/JPY', 'CHF/JPY', 'NZD/CAD', 'NZD/CHF', 'NZD/JPY'] },
    { label: 'Metals/Crypto',pairs: ['XAU/USD', 'XAG/USD', 'BTC/USD', 'ETH/USD'] },
  ];

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-surface border border-border text-text-primary rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent"
    >
      {groups.map((g) => (
        <optgroup key={g.label} label={g.label}>
          {g.pairs.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

// ── Bias Row ───────────────────────────────────────────────────────────────
function BiasRow({ pair, bias, ema9, ema15, price }) {
  const { Icon, color, label } = biasIcon(bias);
  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-surface-hover/30 transition-colors">
      <span className="font-mono text-xs font-bold text-text-primary w-20 flex-shrink-0">{pair}</span>
      <div className="flex items-center gap-1.5 flex-1">
        <Icon size={11} style={{ color }} />
        <span className="text-[10px] font-bold" style={{ color }}>{label}</span>
      </div>
      {price && (
        <div className="flex gap-2 text-[9px] font-mono text-text-muted">
          <span style={{ color: '#58a6ff' }}>E9:{formatPrice(ema9, pair)}</span>
          <span style={{ color: '#e3b341' }}>E15:{formatPrice(ema15, pair)}</span>
        </div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────
export default function ForexPage() {
  const [signals,      setSignals]      = useState([]);
  const [loading,      setLoading]      = useState(false);
  const [isLive,       setIsLive]       = useState(false);
  const [lastScan,     setLastScan]     = useState('');
  const [nextRefresh,  setNextRefresh]  = useState(() => Date.now() + REFRESH_INTERVAL);
  const [expanded,     setExpanded]     = useState(null);
  const [safeOnly,     setSafeOnly]     = useState(false);
  const [activeTab,    setActiveTab]    = useState('signals');
  const [error,        setError]        = useState('');
  const [chartPair,    setChartPair]    = useState('EUR/USD');
  const [chartSignal,  setChartSignal]  = useState(null);
  const [candles,      setCandles]      = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartInterval, setChartInterval] = useState('1h');
  const [trendlines,   setTrendlines]    = useState([]);
  // Journal state
  const [journalEntries, setJournalEntries] = useState([]);
  const [journalStats,   setJournalStats]   = useState(null);
  const [showAddTrade,   setShowAddTrade]   = useState(false);
  const [journalLoading, setJournalLoading] = useState(false);
  const [newTrade, setNewTrade] = useState({
    pair: 'EUR/USD', direction: 'BUY', entry: '', sl: '', tp1: '', tp2: '', tp3: '',
    result: 'OPEN', exit_price: '', pnl_pips: '', rr_achieved: '',
    session: 'London', confluence_score: 0, notes: '',
  });
  const now = useNow();
  const chartTimerRef = useRef(null);

  // ── Fetch SMC signals ────────────────────────────────────────────────
  const fetchSignals = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/api/v1/signals/smart-money-forex`, { signal: AbortSignal.timeout(25000) });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      if (data.status === 'loading') {
        // Backend is warming up — retry in 8 seconds
        setError('Backend warming up… live signals in a few seconds.');
        setTimeout(fetchSignals, 8000);
        return;
      }
      setSignals(data.signals || []);
      setIsLive(true);
      setError('');
      setLastScan(new Date().toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true,
      }));
    } catch (err) {
      console.warn('Backend offline — using demo signals:', err.message);
      setIsLive(false);
      setSignals(DEMO_SIGNALS);
      setError('Backend offline — showing demo signals. Start backend for live data.');
    } finally {
      setLoading(false);
      setNextRefresh(Date.now() + REFRESH_INTERVAL);
    }
  }, []);

  // ── Fetch candles for chart ──────────────────────────────────────────
  const fetchCandles = useCallback(async (pair, interval) => {
    setChartLoading(true);
    try {
      const sym = pair.replace('/', '');
      const [candleRes, tlRes] = await Promise.all([
        fetch(`${API}/api/v1/market/candles?symbol=${sym}&interval=${interval}&outputsize=200`),
        fetch(`${API}/api/v1/market/trendlines?symbol=${sym}&interval=${interval}&outputsize=150`),
      ]);
      if (candleRes.ok) {
        const data = await candleRes.json();
        setCandles(Array.isArray(data) ? data : []);
      } else {
        setCandles([]);
      }
      if (tlRes.ok) {
        const tlData = await tlRes.json();
        setTrendlines(tlData.trendlines || []);
      } else {
        setTrendlines([]);
      }
    } catch (err) {
      console.warn('Candles/trendline fetch failed:', err.message);
      setCandles([]);
      setTrendlines([]);
    } finally {
      setChartLoading(false);
    }
  }, []);

  // ── Signal scan on mount + interval ──────────────────────────────────
  useEffect(() => {
    fetchSignals();
    const id = setInterval(fetchSignals, REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [fetchSignals]);

  // ── Chart fetch on pair/interval change + auto-refresh ───────────────
  useEffect(() => {
    if (activeTab === 'chart') {
      fetchCandles(chartPair, chartInterval);
      clearInterval(chartTimerRef.current);
      chartTimerRef.current = setInterval(() => fetchCandles(chartPair, chartInterval), CHART_REFRESH);
    }
    return () => clearInterval(chartTimerRef.current);
  }, [chartPair, chartInterval, activeTab, fetchCandles]);

  // Set chart signal when pair changes or signals update
  useEffect(() => {
    const sig = signals.find((s) => s.pair === chartPair);
    setChartSignal(sig || null);
  }, [signals, chartPair]);

  // ── When user clicks "Chart" on a signal card ─────────────────────────
  const handleViewChart = useCallback((sig) => {
    setChartPair(sig.pair);
    setChartSignal(sig);
    setActiveTab('chart');
  }, []);

  // ── Journal helpers ──────────────────────────────────────────────────
  const fetchJournal = useCallback(async () => {
    setJournalLoading(true);
    try {
      const [entriesRes, statsRes] = await Promise.all([
        fetch(`${API}/api/v1/journal/entries?limit=100`),
        fetch(`${API}/api/v1/journal/stats`),
      ]);
      if (entriesRes.ok) setJournalEntries(await entriesRes.json());
      if (statsRes.ok)   setJournalStats(await statsRes.json());
    } catch { /* ignore */ }
    setJournalLoading(false);
  }, []);

  useEffect(() => {
    if (activeTab === 'journal') fetchJournal();
  }, [activeTab, fetchJournal]);

  const submitTrade = async () => {
    const body = { ...newTrade };
    ['entry','sl','tp1','tp2','tp3','exit_price','pnl_pips','rr_achieved'].forEach(k => {
      if (body[k] !== '' && body[k] !== null) body[k] = parseFloat(body[k]) || 0;
    });
    body.confluence_score = parseInt(body.confluence_score) || 0;
    try {
      const res = await fetch(`${API}/api/v1/journal/entry`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) { setShowAddTrade(false); fetchJournal(); }
    } catch { /* ignore */ }
  };

  const deleteJournalEntry = async (id) => {
    await fetch(`${API}/api/v1/journal/entry/${id}`, { method: 'DELETE' });
    fetchJournal();
  };

  const filtered  = safeOnly ? signals.filter((s) => s.confidence >= 80) : signals;
  const buyCount  = filtered.filter((s) => s.direction === 'BUY').length;
  const sellCount = filtered.filter((s) => s.direction === 'SELL').length;

  const TABS = [
    { id: 'signals',   label: 'SMC Signals',  count: filtered.length },
    { id: 'orderbook', label: 'Order Book',   count: null },
    { id: 'chart',     label: 'Live Chart',   count: null },
    { id: 'bias',      label: 'HTF Bias',     count: null },
    { id: 'journal',   label: 'Journal',      count: journalStats ? journalStats.total_trades : null },
  ];

  return (
    <div className="p-4 lg:p-5 min-h-screen">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center">
              <Globe size={15} className="text-accent" />
            </div>
            <h1 className="text-xl font-bold text-text-primary">Forex Intelligence</h1>
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold ${
              isLive ? 'bg-positive-subtle text-positive' : 'bg-warning-subtle text-warning'
            }`}>
              {isLive ? <Wifi size={8} /> : <WifiOff size={8} />}
              {isLive ? 'LIVE' : 'DEMO'}
            </div>
          </div>
          <p className="text-[11px] text-text-muted ml-10 mt-0.5">
            ICT / SMC — FVG + Liquidity Sweep + EMA 9/15/200 — ADX + Session + ATR
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="text-[10px] text-text-muted flex items-center gap-1">
            <Clock size={9} /> {now} IST
          </div>
          {lastScan && <Countdown nextRefresh={nextRefresh} />}
          <button
            onClick={() => setSafeOnly((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all ${
              safeOnly ? 'bg-positive text-white' : 'bg-surface border border-border text-text-secondary hover:border-positive hover:text-positive'
            }`}
          >
            <Shield size={10} /> {safeOnly ? '80%+ Only' : 'All Signals'}
          </button>
          <button
            onClick={fetchSignals}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold bg-accent-subtle text-accent hover:bg-accent hover:text-white transition-all"
          >
            <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
            {loading ? 'Scanning…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* ── Error banner ───────────────────────────────────────── */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg p-3 bg-warning-subtle border border-warning/30">
          <AlertTriangle size={13} className="text-warning flex-shrink-0" />
          <span className="text-[11px] text-warning">{error}</span>
        </div>
      )}

      {/* ── Stats ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Total Signals',  val: filtered.length, icon: Zap,          col: '#388bfd' },
          { label: 'BUY Setups',     val: buyCount,        icon: TrendingUp,   col: '#3fb950' },
          { label: 'SELL Setups',    val: sellCount,       icon: TrendingDown, col: '#f85149' },
          { label: 'Avg Confidence', val: filtered.length
              ? Math.round(filtered.reduce((a, s) => a + s.confidence, 0) / filtered.length) + '%'
              : '—',
            icon: Shield, col: '#e3b341' },
        ].map((s, i) => (
          <div key={i} className="glass-card p-3 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center" style={{ background: s.col + '22' }}>
              <s.icon size={14} style={{ color: s.col }} />
            </div>
            <div>
              <div className="text-xl font-bold font-mono text-text-primary">{s.val}</div>
              <div className="text-[10px] text-text-muted">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Tabs ───────────────────────────────────────────────── */}
      <div className="overflow-x-auto -mx-4 px-4 lg:mx-0 lg:px-0 mb-4">
        <div className="flex gap-1 p-1 bg-surface/50 rounded-xl w-max min-w-full sm:w-fit">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-1.5 px-3 sm:px-4 py-2.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
                activeTab === t.id
                  ? 'bg-accent text-white shadow-[0_0_12px_rgba(56,139,253,0.4)]'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {t.label}
              {t.count !== null && (
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                  activeTab === t.id ? 'bg-white/20' : 'bg-surface text-text-muted'
                }`}>{t.count}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── SMC Signals Tab ────────────────────────────────────── */}
      {activeTab === 'signals' && (
        <div>
          {loading && signals.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <RefreshCw size={28} className="text-accent animate-spin mx-auto mb-3" />
              <div className="text-text-secondary text-sm">Scanning forex markets…</div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <Activity size={28} className="text-text-muted mx-auto mb-3" />
              <div className="text-text-secondary text-sm">No setups found right now</div>
              <div className="text-text-muted text-xs mt-1">
                {safeOnly ? 'Try disabling "80%+ Only" filter' : 'Check back in 15 min'}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {filtered.map((sig, i) => (
                <SignalCard
                  key={`${sig.pair}-${i}`}
                  sig={sig}
                  expanded={expanded === i}
                  onToggle={() => setExpanded(expanded === i ? null : i)}
                  onViewChart={handleViewChart}
                />
              ))}
            </div>
          )}
          <div className="mt-4 flex items-start gap-2 rounded-lg p-3 bg-surface/60 border border-border/40">
            <AlertTriangle size={12} className="text-warning flex-shrink-0 mt-0.5" />
            <div className="text-[10px] text-text-muted leading-relaxed">
              <strong className="text-warning">Risk Disclaimer:</strong> Yeh signals AI analysis pe based hain — financial advice nahi hain.
              Har trade pe max 1-2% capital risk karo. Data: yfinance (~15 min delayed).
            </div>
          </div>
        </div>
      )}

      {/* ── Order Book Tab ─────────────────────────────────────── */}
      {activeTab === 'orderbook' && (
        <div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <OrderBook
              symbol={chartPair.replace('/', '')}
              displaySymbol={chartPair}
            />
            {/* Quick pair switcher for order book */}
            <div className="glass-card p-4">
              <div className="text-sm font-semibold text-text-primary mb-3">Switch Pair</div>
              <div className="grid grid-cols-2 gap-2">
                {['EUR/USD','GBP/USD','USD/JPY','AUD/USD','USD/CAD','NZD/USD','GBP/JPY','USD/CHF'].map((p) => (
                  <button
                    key={p}
                    onClick={() => setChartPair(p)}
                    className={`px-3 py-2 rounded-lg text-xs font-mono font-bold transition-all ${
                      chartPair === p
                        ? 'bg-accent text-white shadow-[0_0_10px_rgba(56,139,253,0.3)]'
                        : 'bg-surface border border-border text-text-secondary hover:border-accent hover:text-accent'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <div className="mt-4 p-3 rounded-lg bg-surface/60 border border-border/40">
                <div className="text-[10px] text-text-muted leading-relaxed">
                  <strong className="text-warning text-[10px]">Note:</strong> Forex is OTC — no centralised order book exists.
                  Depth is simulated based on real prices and typical interbank spread distributions.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Live Chart Tab ─────────────────────────────────────── */}
      {activeTab === 'chart' && (
        <div className="glass-card p-4">
          {/* Controls */}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="flex items-center gap-2">
              <BarChart2 size={14} className="text-accent" />
              <span className="text-sm font-semibold text-text-primary">Live Chart</span>
            </div>
            <PairSelector value={chartPair} onChange={setChartPair} />
            <div className="flex gap-1">
              {['15m', '1h', '4h', '1d'].map((iv) => (
                <button
                  key={iv}
                  onClick={() => setChartInterval(iv)}
                  className={`px-3 py-1 rounded-lg text-[10px] font-bold transition-all ${
                    chartInterval === iv
                      ? 'bg-accent text-white'
                      : 'bg-surface border border-border text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {iv}
                </button>
              ))}
            </div>
            <button
              onClick={() => fetchCandles(chartPair, chartInterval)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-bold bg-accent-subtle text-accent hover:bg-accent hover:text-white transition-all ml-auto"
            >
              <RefreshCw size={9} className={chartLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {/* Signal quick-select from available signals */}
          {signals.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              <span className="text-[10px] text-text-muted self-center">Jump to signal:</span>
              {signals.slice(0, 8).map((s, i) => {
                const isBuy = s.direction === 'BUY';
                return (
                  <button
                    key={i}
                    onClick={() => handleViewChart(s)}
                    className={`text-[9px] px-2 py-1 rounded-lg font-bold transition-all ${
                      chartPair === s.pair
                        ? (isBuy ? 'bg-positive text-white' : 'bg-negative text-white')
                        : 'bg-surface border border-border text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {s.pair} {isBuy ? '▲' : '▼'}
                  </button>
                );
              })}
            </div>
          )}

          <ForexChart
            pair={chartPair}
            signal={chartSignal}
            candles={candles}
            loading={chartLoading}
            trendlines={trendlines}
          />

          {candles.length === 0 && !chartLoading && (
            <div className="mt-3 text-center text-[11px] text-text-muted">
              No candle data for {chartPair}. Make sure the backend is running.
            </div>
          )}
        </div>
      )}

      {/* ── HTF Bias Tab ───────────────────────────────────────── */}
      {activeTab === 'bias' && (
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 size={14} className="text-purple" />
            <span className="text-sm font-semibold text-text-primary">4H Higher Timeframe Bias</span>
            <span className="text-[10px] text-text-muted">EMA 9 / 15 / 200</span>
          </div>

          {signals.length > 0 ? (
            <div className="divide-y divide-border/20">
              {signals.map((s, i) => (
                <BiasRow key={i}
                  pair={s.pair} bias={s.htf_bias}
                  ema9={s.ema9} ema15={s.ema15} ema200={s.ema200}
                  price={s.current_price || s.entry}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-text-muted text-sm">
              {loading ? 'Loading bias data…' : 'Refresh to load HTF data'}
            </div>
          )}

          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            {[
              { label: 'Bullish Pairs', val: signals.filter((s) => s.htf_bias === 'bullish').length, color: '#3fb950' },
              { label: 'Bearish Pairs', val: signals.filter((s) => s.htf_bias === 'bearish').length, color: '#f85149' },
              { label: 'Neutral Pairs', val: signals.filter((s) => s.htf_bias === 'neutral').length, color: '#8b949e' },
            ].map(({ label, val, color }) => (
              <div key={label} className="rounded-lg p-2" style={{ background: color + '15' }}>
                <div className="text-xl font-bold font-mono" style={{ color }}>{val}</div>
                <div className="text-[9px] text-text-muted">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Journal Tab ────────────────────────────────────────── */}
      {activeTab === 'journal' && (
        <div className="space-y-4">
          {/* Stats bar */}
          {journalStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Total Trades', val: journalStats.total_trades,                      col: '#388bfd' },
                { label: 'Win Rate',     val: journalStats.win_rate + '%',                    col: '#3fb950' },
                { label: 'Avg R:R',      val: journalStats.avg_rr,                            col: '#e3b341' },
                { label: 'Total Pips',   val: (journalStats.total_pips > 0 ? '+' : '') + journalStats.total_pips, col: journalStats.total_pips >= 0 ? '#3fb950' : '#f85149' },
              ].map((s, i) => (
                <div key={i} className="glass-card p-3 flex items-center gap-3">
                  <div>
                    <div className="text-xl font-bold font-mono" style={{ color: s.col }}>{s.val}</div>
                    <div className="text-[10px] text-text-muted">{s.label}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Add trade button */}
          <div className="flex justify-between items-center">
            <span className="text-sm font-semibold text-text-primary">Trade Log</span>
            <button
              onClick={() => setShowAddTrade((v) => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold bg-accent text-white hover:bg-accent/80 transition-all"
            >
              <PlusCircle size={11} /> Add Trade
            </button>
          </div>

          {/* Add trade form */}
          {showAddTrade && (
            <div className="glass-card p-4 space-y-3">
              <div className="text-xs font-bold text-text-primary mb-2">Log New Trade</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {[
                  { key: 'pair',      label: 'Pair',   type: 'text'   },
                  { key: 'direction', label: 'Dir',    type: 'select', opts: ['BUY','SELL'] },
                  { key: 'session',   label: 'Session',type: 'select', opts: ['London','NY','Asian','Overlap'] },
                  { key: 'entry',     label: 'Entry',  type: 'number' },
                  { key: 'sl',        label: 'SL',     type: 'number' },
                  { key: 'tp1',       label: 'TP1',    type: 'number' },
                  { key: 'result',    label: 'Result', type: 'select', opts: ['OPEN','WIN','LOSS','BREAKEVEN'] },
                  { key: 'pnl_pips',  label: 'PnL Pips',type:'number' },
                  { key: 'rr_achieved',label:'R:R',    type: 'number' },
                ].map(({ key, label, type, opts }) => (
                  <div key={key}>
                    <div className="text-[9px] text-text-muted mb-0.5">{label}</div>
                    {type === 'select' ? (
                      <select
                        value={newTrade[key]}
                        onChange={(e) => setNewTrade((t) => ({ ...t, [key]: e.target.value }))}
                        className="w-full bg-surface border border-border rounded-lg px-2 py-1 text-xs text-text-primary"
                      >
                        {opts.map((o) => <option key={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input
                        type={type}
                        value={newTrade[key]}
                        onChange={(e) => setNewTrade((t) => ({ ...t, [key]: e.target.value }))}
                        className="w-full bg-surface border border-border rounded-lg px-2 py-1 text-xs text-text-primary"
                        placeholder="—"
                      />
                    )}
                  </div>
                ))}
              </div>
              <div>
                <div className="text-[9px] text-text-muted mb-0.5">Notes</div>
                <input
                  type="text"
                  value={newTrade.notes}
                  onChange={(e) => setNewTrade((t) => ({ ...t, notes: e.target.value }))}
                  className="w-full bg-surface border border-border rounded-lg px-2 py-1 text-xs text-text-primary"
                  placeholder="Optional notes…"
                />
              </div>
              <div className="flex gap-2">
                <button onClick={submitTrade} className="px-4 py-1.5 rounded-lg bg-positive text-white text-xs font-bold">Save</button>
                <button onClick={() => setShowAddTrade(false)} className="px-4 py-1.5 rounded-lg bg-surface border border-border text-text-secondary text-xs font-bold">Cancel</button>
              </div>
            </div>
          )}

          {/* Trade table */}
          {journalLoading ? (
            <div className="text-center py-8 text-text-muted text-sm">Loading journal…</div>
          ) : journalEntries.length === 0 ? (
            <div className="glass-card p-10 text-center text-text-muted text-sm">
              <BookOpen size={28} className="mx-auto mb-3 opacity-30" />
              No trades logged yet. Click "Add Trade" to start.
            </div>
          ) : (
            <div className="glass-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="border-b border-border/30 text-text-muted text-[10px] uppercase tracking-wider">
                      {['Pair','Dir','Session','Entry','SL','TP1','Result','Pips','R:R','Notes',''].map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/20">
                    {journalEntries.map((e) => {
                      const isBuy = e.direction === 'BUY';
                      const resColor = e.result === 'WIN' ? '#3fb950' : e.result === 'LOSS' ? '#f85149' : '#e3b341';
                      return (
                        <tr key={e.id} className="hover:bg-surface-hover/20 transition-colors">
                          <td className="px-3 py-2 font-mono font-bold text-text-primary">{e.pair}</td>
                          <td className="px-3 py-2">
                            <span className={`px-1.5 py-0.5 rounded font-bold text-[9px] ${isBuy ? 'bg-positive/20 text-positive' : 'bg-negative/20 text-negative'}`}>
                              {e.direction}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-text-secondary">{e.session || '—'}</td>
                          <td className="px-3 py-2 font-mono text-text-primary">{e.entry}</td>
                          <td className="px-3 py-2 font-mono text-negative">{e.sl}</td>
                          <td className="px-3 py-2 font-mono text-positive">{e.tp1}</td>
                          <td className="px-3 py-2">
                            <span className="font-bold" style={{ color: resColor }}>{e.result}</span>
                          </td>
                          <td className="px-3 py-2 font-mono" style={{ color: (e.pnl_pips || 0) >= 0 ? '#3fb950' : '#f85149' }}>
                            {e.pnl_pips != null ? (e.pnl_pips >= 0 ? '+' : '') + e.pnl_pips : '—'}
                          </td>
                          <td className="px-3 py-2 font-mono text-text-secondary">{e.rr_achieved ?? '—'}</td>
                          <td className="px-3 py-2 text-text-muted max-w-[120px] truncate">{e.notes || '—'}</td>
                          <td className="px-3 py-2">
                            <button onClick={() => deleteJournalEntry(e.id)} className="text-text-muted hover:text-negative transition-colors">
                              <Trash2 size={11} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Monthly breakdown */}
          {journalStats?.monthly_breakdown?.length > 0 && (
            <div className="glass-card p-4">
              <div className="text-xs font-bold text-text-secondary mb-3">Monthly Breakdown</div>
              <div className="space-y-1.5">
                {journalStats.monthly_breakdown.map((m) => (
                  <div key={m.month} className="flex items-center gap-3 text-[11px]">
                    <span className="text-text-muted w-16 font-mono">{m.month}</span>
                    <span className="text-text-secondary w-12">{m.trades} trades</span>
                    <span className="text-text-secondary w-14">{m.wins} wins</span>
                    <span className="font-mono font-bold" style={{ color: m.pips >= 0 ? '#3fb950' : '#f85149' }}>
                      {m.pips >= 0 ? '+' : ''}{m.pips} pips
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
