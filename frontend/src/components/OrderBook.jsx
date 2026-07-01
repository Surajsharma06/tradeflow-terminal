import { useState, useEffect, useRef, useCallback } from 'react';
import { Activity, Wifi, WifiOff, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { API } from '../lib/api';

const WS_BASE = API
  ? API.replace(/^https?/, 'wss').replace(/^http/, 'ws')
  : (typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
      : 'ws://localhost:8000');

function fmt(price, symbol) {
  if (!price) return '—';
  if (symbol?.includes('JPY') || symbol?.includes('XAG')) return price.toFixed(3);
  if (symbol === 'XAU/USD') return price.toFixed(2);
  if (symbol === 'BTC/USD' || symbol === 'ETH/USD') return price.toFixed(2);
  return price.toFixed(5);
}

function fmtVol(v) {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)     return `${(v / 1_000).toFixed(0)}K`;
  return v;
}

function DepthBar({ volume, maxVol, side }) {
  const pct = maxVol > 0 ? Math.min((volume / maxVol) * 100, 100) : 0;
  return (
    <div className="absolute inset-y-0 w-full rounded-sm overflow-hidden">
      <div
        className={`h-full transition-all duration-300 ${side === 'bid' ? 'bg-positive/12' : 'bg-negative/12'}`}
        style={{ width: `${pct}%`, [side === 'bid' ? 'marginLeft' : 'marginLeft']: side === 'ask' ? 'auto' : 0 }}
      />
    </div>
  );
}

function PriceRow({ level, maxVol, side, highlight }) {
  return (
    <div className={`relative flex items-center justify-between px-2 py-[3px] rounded-sm transition-colors ${highlight ? (side === 'bid' ? 'bg-positive/10' : 'bg-negative/10') : ''}`}>
      <DepthBar volume={level.volume} maxVol={maxVol} side={side} />
      <span className={`relative z-10 font-mono text-[11px] font-semibold ${side === 'bid' ? 'text-positive' : 'text-negative'}`}>
        {fmt(level.price, highlight)}
      </span>
      <span className="relative z-10 font-mono text-[10px] text-text-muted">{fmtVol(level.volume)}</span>
    </div>
  );
}

export default function OrderBook({ symbol = 'EURUSD', displaySymbol = 'EUR/USD', className = '' }) {
  const [data,      setData]      = useState(null);
  const [status,    setStatus]    = useState('connecting'); // connecting | live | polling | error
  const [lastTick,  setLastTick]  = useState(null);
  const wsRef   = useRef(null);
  const pollRef = useRef(null);

  const fetchRest = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v1/market/orderbook?symbol=${symbol}&levels=12`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setData(d);
      setLastTick(Date.now());
      setStatus('polling');
    } catch {
      setStatus('error');
    }
  }, [symbol]);

  // Try WebSocket first, fall back to REST polling
  useEffect(() => {
    setData(null);
    setStatus('connecting');

    const wsUrl = `${WS_BASE}/ws/orderbook?symbol=${symbol}`;
    let ws;

    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setStatus('live');

      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          setData(d);
          setLastTick(Date.now());
        } catch { /* ignore parse errors */ }
      };

      ws.onerror = () => {
        setStatus('polling');
        fetchRest();
        pollRef.current = setInterval(fetchRest, 2000);
      };

      ws.onclose = () => {
        if (status !== 'error') {
          setStatus('polling');
          fetchRest();
          pollRef.current = setInterval(fetchRest, 2000);
        }
      };
    } catch {
      setStatus('polling');
      fetchRest();
      pollRef.current = setInterval(fetchRest, 2000);
    }

    return () => {
      ws?.close();
      clearInterval(pollRef.current);
    };
  }, [symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  const maxBidVol = data ? Math.max(...data.bids.map(b => b.volume)) : 1;
  const maxAskVol = data ? Math.max(...data.asks.map(a => a.volume)) : 1;
  const maxVol    = Math.max(maxBidVol, maxAskVol);

  const imbalance   = data?.imbalance ?? 0.5;
  const bidPressure = Math.round(imbalance * 100);
  const askPressure = 100 - bidPressure;
  const bullish     = imbalance >= 0.5;

  return (
    <div className={`glass-card overflow-hidden ${className}`}>
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center flex-shrink-0">
            <Activity size={14} className="text-accent" />
          </div>
          <div>
            <div className="text-sm font-bold text-text-primary leading-tight">Order Book</div>
            <div className="text-[10px] text-text-muted">{displaySymbol}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {status === 'live' && (
            <span className="flex items-center gap-1 text-[9px] font-bold text-positive">
              <span className="w-1.5 h-1.5 rounded-full bg-positive animate-pulse" />
              LIVE
            </span>
          )}
          {status === 'polling' && (
            <span className="flex items-center gap-1 text-[9px] font-bold text-warning">
              <RefreshCw size={8} className="animate-spin" />
              POLLING
            </span>
          )}
          {status === 'connecting' && (
            <span className="flex items-center gap-1 text-[9px] text-text-muted">
              <RefreshCw size={8} className="animate-spin" />
              Connecting…
            </span>
          )}
          {status === 'error' && (
            <span className="flex items-center gap-1 text-[9px] text-negative">
              <WifiOff size={8} /> Offline
            </span>
          )}
        </div>
      </div>

      {!data ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <RefreshCw size={22} className="text-accent animate-spin" />
          <span className="text-xs text-text-muted">Fetching live depth…</span>
        </div>
      ) : (
        <>
          {/* ── Spread / Mid Price ───────────────────────────── */}
          <div className="flex items-center justify-between px-4 py-2 bg-surface/50">
            <div className="text-center">
              <div className="text-[9px] text-text-muted mb-0.5">BID</div>
              <div className="font-mono text-sm font-bold text-positive">{fmt(data.bid, displaySymbol)}</div>
            </div>
            <div className="text-center">
              <div className="text-[9px] text-text-muted mb-0.5">SPREAD</div>
              <div className="font-mono text-xs font-bold text-accent">{data.spread_pips} pips</div>
            </div>
            <div className="text-center">
              <div className="text-[9px] text-text-muted mb-0.5">ASK</div>
              <div className="font-mono text-sm font-bold text-negative">{fmt(data.ask, displaySymbol)}</div>
            </div>
          </div>

          {/* ── Imbalance Bar ────────────────────────────────── */}
          <div className="px-4 py-2 border-b border-border/30">
            <div className="flex items-center justify-between text-[9px] mb-1">
              <span className="text-positive font-bold flex items-center gap-0.5">
                <TrendingUp size={8} /> Bids {bidPressure}%
              </span>
              <span className="text-text-muted">{bullish ? '▲ Buy Pressure' : '▼ Sell Pressure'}</span>
              <span className="text-negative font-bold flex items-center gap-0.5">
                Asks {askPressure}% <TrendingDown size={8} />
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-surface overflow-hidden flex">
              <div
                className="h-full bg-positive transition-all duration-500"
                style={{ width: `${bidPressure}%` }}
              />
              <div
                className="h-full bg-negative transition-all duration-500"
                style={{ width: `${askPressure}%` }}
              />
            </div>
          </div>

          {/* ── Depth Table ──────────────────────────────────── */}
          <div className="px-2 pb-2">
            <div className="grid grid-cols-2 gap-1 mt-2">
              {/* Asks — shown top to bottom (highest ask first, reversed) */}
              <div className="space-y-0.5">
                <div className="flex justify-between px-2 mb-1">
                  <span className="text-[9px] text-text-muted font-bold uppercase">Price</span>
                  <span className="text-[9px] text-negative font-bold uppercase">Ask Vol</span>
                </div>
                {[...data.asks].reverse().map((a, i) => (
                  <PriceRow key={i} level={a} maxVol={maxVol} side="ask" />
                ))}
              </div>

              {/* Bids */}
              <div className="space-y-0.5">
                <div className="flex justify-between px-2 mb-1">
                  <span className="text-[9px] text-positive font-bold uppercase">Bid Vol</span>
                  <span className="text-[9px] text-text-muted font-bold uppercase">Price</span>
                </div>
                {data.bids.map((b, i) => (
                  <div key={i} className="relative flex items-center justify-between px-2 py-[3px] rounded-sm">
                    <DepthBar volume={b.volume} maxVol={maxVol} side="bid" />
                    <span className="relative z-10 font-mono text-[10px] text-text-muted">{fmtVol(b.volume)}</span>
                    <span className="relative z-10 font-mono text-[11px] font-semibold text-positive">{fmt(b.price, displaySymbol)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Total volumes */}
            <div className="flex justify-between mt-2 pt-2 border-t border-border/20 px-2">
              <div className="text-center">
                <div className="text-[9px] text-text-muted">Total Ask</div>
                <div className="font-mono text-[10px] font-bold text-negative">{fmtVol(data.total_ask_vol)}</div>
              </div>
              <div className="text-center">
                <div className="text-[9px] text-text-muted">Mid Price</div>
                <div className="font-mono text-[10px] font-bold text-text-primary">{fmt(data.price, displaySymbol)}</div>
              </div>
              <div className="text-center">
                <div className="text-[9px] text-text-muted">Total Bid</div>
                <div className="font-mono text-[10px] font-bold text-positive">{fmtVol(data.total_bid_vol)}</div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
