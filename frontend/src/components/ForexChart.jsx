/**
 * ForexChart — TradingView lightweight-charts v5 candlestick chart
 * Shows OHLCV candles with Entry, SL, TP1, TP2, TP3 price lines
 * and a signal box overlay.
 */

import { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, LineSeries, LineStyle } from 'lightweight-charts';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

// ── Session config ─────────────────────────────────────────────────────────
const SESSION_CONFIG = {
  Asian:   { color: '#9333ea', label: 'Asian Session',          hours: '00:00–08:00 UTC' },
  London:  { color: '#3b82f6', label: 'London Session',         hours: '08:00–16:00 UTC' },
  NY:      { color: '#10b981', label: 'New York Session',       hours: '13:00–21:00 UTC' },
  Overlap: { color: '#f59e0b', label: 'London–NY Overlap',     hours: '13:00–16:00 UTC' },
  'Off-hours': { color: '#6b7280', label: 'Off-Hours',          hours: 'Low liquidity' },
};

function getActiveSessions() {
  const h = new Date().getUTCHours();
  const sessions = [];
  if (h >= 0  && h < 8)  sessions.push('Asian');
  if (h >= 8  && h < 16) sessions.push('London');
  if (h >= 13 && h < 21) sessions.push('NY');
  if (h >= 13 && h < 16) sessions.push('Overlap');
  return sessions.length ? sessions : ['Off-hours'];
}

// ── Session indicator ──────────────────────────────────────────────────────
function SessionBadge({ name }) {
  const cfg = SESSION_CONFIG[name] || SESSION_CONFIG['Off-hours'];
  return (
    <div
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold"
      style={{ background: cfg.color + '22', color: cfg.color, border: `1px solid ${cfg.color}44` }}
    >
      <Activity size={10} />
      <span>{cfg.label}</span>
      <span className="text-[9px] opacity-70">{cfg.hours}</span>
    </div>
  );
}

// ── Signal overlay box ─────────────────────────────────────────────────────
function SignalBox({ signal, pair }) {
  if (!signal) return null;
  const isBuy = signal.direction === 'BUY';
  const fmt = (v) => {
    if (!v && v !== 0) return '—';
    const p = pair?.includes('JPY') ? 3 : (pair?.includes('XAU') ? 2 : 5);
    return Number(v).toFixed(p);
  };

  return (
    <div
      className="absolute top-3 right-3 z-10 rounded-xl p-3 text-xs min-w-[170px] shadow-2xl"
      style={{
        background: 'rgba(13,17,23,0.92)',
        border: `1px solid ${isBuy ? '#3fb95055' : '#f8514955'}`,
        backdropFilter: 'blur(8px)',
      }}
    >
      {/* Direction badge */}
      <div className="flex items-center justify-between mb-2">
        <div
          className="flex items-center gap-1.5 px-2 py-1 rounded-lg font-bold text-[11px]"
          style={{ background: isBuy ? '#3fb95033' : '#f8514933', color: isBuy ? '#3fb950' : '#f85149' }}
        >
          {isBuy ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
          {signal.direction}
        </div>
        <div className="text-right">
          <div className="text-base font-bold font-mono" style={{ color: signal.confidence >= 75 ? '#3fb950' : signal.confidence >= 60 ? '#e3b341' : '#f85149' }}>
            {signal.confidence}%
          </div>
          <div className="text-[8px] text-gray-500">CONFIDENCE</div>
        </div>
      </div>

      {/* Price levels */}
      <div className="space-y-1">
        {[
          { label: 'ENTRY', val: signal.entry,     color: '#60a5fa' },
          { label: 'SL',    val: signal.stop_loss,  color: '#f87171' },
          { label: 'TP1',   val: signal.tp1,        color: '#4ade80' },
          { label: 'TP2',   val: signal.tp2,        color: '#22c55e' },
          { label: 'TP3',   val: signal.tp3,        color: '#16a34a' },
        ].map(({ label, val, color }) => (
          <div key={label} className="flex justify-between items-center">
            <span className="text-[9px] text-gray-500 w-8">{label}</span>
            <span className="font-mono text-[10px] font-bold" style={{ color }}>{fmt(val)}</span>
          </div>
        ))}
      </div>

      {/* ADX / RSI */}
      <div className="flex justify-between mt-2 pt-2 border-t border-gray-700">
        <span className="text-[9px] text-gray-500">ADX <span className="text-gray-300 font-mono">{signal.adx?.toFixed(1)}</span></span>
        <span className="text-[9px] text-gray-500">RSI <span className="text-gray-300 font-mono">{signal.rsi?.toFixed(1)}</span></span>
      </div>
    </div>
  );
}

// ── Main chart component ────────────────────────────────────────────────────
export default function ForexChart({ pair, signal, candles, loading, trendlines = [] }) {
  const containerRef    = useRef(null);
  const chartRef        = useRef(null);
  const seriesRef       = useRef(null);
  const linesRef        = useRef([]);
  const trendSeriesRef  = useRef([]);
  const sessions        = getActiveSessions();

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0d1117' },
        textColor:  '#c9d1d9',
      },
      grid: {
        vertLines: { color: '#21262d' },
        horzLines: { color: '#21262d' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#30363d',
      },
      timeScale: {
        borderColor:   '#30363d',
        timeVisible:   true,
        secondsVisible: false,
      },
      width:  containerRef.current.clientWidth,
      height: 420,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:          '#3fb950',
      downColor:        '#f85149',
      borderUpColor:    '#3fb950',
      borderDownColor:  '#f85149',
      wickUpColor:      '#3fb950',
      wickDownColor:    '#f85149',
    });

    chartRef.current  = chart;
    seriesRef.current = candleSeries;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current  = null;
      seriesRef.current = null;
    };
  }, []);

  // Update candle data
  useEffect(() => {
    if (!seriesRef.current || !candles?.length) return;

    // Remove old price lines
    linesRef.current.forEach((l) => {
      try { seriesRef.current.removePriceLine(l); } catch { /* ignore */ }
    });
    linesRef.current = [];

    const sorted = [...candles].sort((a, b) => a.time - b.time);
    seriesRef.current.setData(sorted);
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Update price lines when signal changes
  useEffect(() => {
    if (!seriesRef.current) return;

    // Remove existing lines
    linesRef.current.forEach((l) => {
      try { seriesRef.current.removePriceLine(l); } catch { /* ignore */ }
    });
    linesRef.current = [];

    if (!signal) return;

    const lineDefs = [
      { price: signal.entry,     color: '#60a5fa', title: 'ENTRY',  lineWidth: 2, lineStyle: LineStyle.Solid },
      { price: signal.stop_loss, color: '#f87171', title: 'SL',     lineWidth: 2, lineStyle: LineStyle.Solid },
      { price: signal.tp1,       color: '#4ade80', title: 'TP1',    lineWidth: 1, lineStyle: LineStyle.Dashed },
      { price: signal.tp2,       color: '#22c55e', title: 'TP2',    lineWidth: 1, lineStyle: LineStyle.Dashed },
      { price: signal.tp3,       color: '#16a34a', title: 'TP3',    lineWidth: 1, lineStyle: LineStyle.Dotted },
    ];

    const created = lineDefs
      .filter((d) => d.price != null && !isNaN(d.price))
      .map((d) =>
        seriesRef.current.createPriceLine({
          price:            d.price,
          color:            d.color,
          lineWidth:        d.lineWidth,
          lineStyle:        d.lineStyle,
          axisLabelVisible: true,
          title:            d.title,
        })
      );

    linesRef.current = created;
  }, [signal]);

  // Draw trendlines as LineSeries
  useEffect(() => {
    if (!chartRef.current) return;

    // Remove old trendline series
    trendSeriesRef.current.forEach((s) => {
      try { chartRef.current.removeSeries(s); } catch { /* ignore */ }
    });
    trendSeriesRef.current = [];

    if (!trendlines?.length || !candles?.length) return;

    trendlines.forEach((tl) => {
      const isSupport = tl.type === 'support';
      const color     = isSupport ? '#4ade80' : '#f87171';

      const series = chartRef.current.addSeries(LineSeries, {
        color,
        lineWidth:        1,
        lineStyle:        LineStyle.Dashed,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });

      const pts = [
        { time: tl.p1.time,       value: tl.p1.price },
        { time: tl.p2.time,       value: tl.p2.price },
        { time: tl.extended.time, value: tl.extended.price },
      ]
        .filter((p) => p.value > 0 && p.time > 0)
        .sort((a, b) => a.time - b.time);

      // Deduplicate by time
      const unique = pts.filter((p, i) => i === 0 || p.time !== pts[i - 1].time);

      if (unique.length >= 2) {
        series.setData(unique);
        trendSeriesRef.current.push(series);
      } else {
        chartRef.current.removeSeries(series);
      }
    });
  }, [trendlines, candles]);

  return (
    <div className="flex flex-col gap-2">
      {/* Session indicator bar */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Active Sessions:</span>
        {sessions.map((s) => (
          <SessionBadge key={s} name={s} />
        ))}
      </div>

      {/* Chart container */}
      <div className="relative rounded-xl overflow-hidden border border-[#21262d]">
        {loading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#0d1117]/80">
            <div className="text-center">
              <Activity size={24} className="text-blue-400 animate-pulse mx-auto mb-2" />
              <div className="text-sm text-gray-400">Loading candles…</div>
            </div>
          </div>
        )}
        <SignalBox signal={signal} pair={pair} />
        <div ref={containerRef} style={{ width: '100%', height: '420px' }} />
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-[10px]">
        {signal && [
          { color: '#60a5fa', label: 'Entry' },
          { color: '#f87171', label: 'Stop Loss' },
          { color: '#4ade80', label: 'TP1' },
          { color: '#22c55e', label: 'TP2' },
          { color: '#16a34a', label: 'TP3' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-5 h-0.5 rounded" style={{ background: color }} />
            <span className="text-gray-500">{label}</span>
          </div>
        ))}
        {trendlines?.length > 0 && (
          <>
            <div className="flex items-center gap-1">
              <div className="w-5 h-0.5 rounded" style={{ background: '#4ade80', borderTop: '1px dashed #4ade80' }} />
              <span className="text-gray-500">Support TL</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-5 h-0.5 rounded" style={{ background: '#f87171', borderTop: '1px dashed #f87171' }} />
              <span className="text-gray-500">Resistance TL</span>
            </div>
            <span className="text-gray-600 ml-1">{trendlines.length} trendlines</span>
          </>
        )}
      </div>
    </div>
  );
}
