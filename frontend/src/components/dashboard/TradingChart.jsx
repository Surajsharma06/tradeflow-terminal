import { useRef, useEffect, useState, useCallback } from 'react';
import { createChart } from 'lightweight-charts';
import { ChevronDown, Maximize2, Minimize2, RefreshCw } from 'lucide-react';

// ── Symbols ───────────────────────────────────────────────────────
const SYMBOLS = [
  { label: 'NIFTY 50', value: 'NIFTY' },
  { label: 'SENSEX', value: 'SENSEX' },
  { label: 'NIFTY BANK', value: 'BANKNIFTY' },
  { label: 'RELIANCE', value: 'RELIANCE' },
  { label: 'TCS', value: 'TCS' },
  { label: 'BTC/USDT', value: 'BTCUSDT' },
];

const TIMEFRAMES = ['1m', '5m', '15m', '1H', '4H', '1D', '1W'];

// ── Generate mock OHLCV data ──────────────────────────────────────
function generateOHLCV(count = 120) {
  const data = [];
  const volumeData = [];
  let open = 24500 + Math.random() * 500;
  const now = Math.floor(Date.now() / 1000);
  const interval = 86400; // daily

  for (let i = 0; i < count; i++) {
    const time = now - (count - i) * interval;
    const change = (Math.random() - 0.48) * 200;
    const high = open + Math.abs(change) + Math.random() * 100;
    const low = open - Math.abs(change) - Math.random() * 100;
    const close = open + change;
    const volume = Math.floor(Math.random() * 5000000 + 1000000);

    data.push({
      time,
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
    });

    volumeData.push({
      time,
      value: volume,
      color: close >= open ? 'rgba(38, 166, 154, 0.35)' : 'rgba(239, 83, 80, 0.35)',
    });

    open = close;
  }

  return { candlestick: data, volume: volumeData };
}

// ══════════════════════════════════════════════════════════════════
//  TRADING CHART COMPONENT
// ══════════════════════════════════════════════════════════════════
export default function TradingChart() {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candlestickSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  const [selectedSymbol, setSelectedSymbol] = useState(SYMBOLS[0]);
  const [selectedTimeframe, setSelectedTimeframe] = useState('1D');
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // ── Create chart ────────────────────────────────────────────────
  const initChart = useCallback(() => {
    if (!chartContainerRef.current) return;

    // Cleanup previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const container = chartContainerRef.current;

    const chart = createChart(container, {
      layout: {
        background: { color: 'transparent' },
        textColor: '#8b949e',
        fontFamily: "'Inter', sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(33, 38, 45, 0.5)' },
        horzLines: { color: 'rgba(33, 38, 45, 0.5)' },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: 'rgba(56, 139, 253, 0.4)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#388bfd',
        },
        horzLine: {
          color: 'rgba(56, 139, 253, 0.4)',
          width: 1,
          style: 2,
          labelBackgroundColor: '#388bfd',
        },
      },
      rightPriceScale: {
        borderColor: 'rgba(33, 38, 45, 0.6)',
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
      timeScale: {
        borderColor: 'rgba(33, 38, 45, 0.6)',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScale: { axisPressedMouseMove: true },
      handleScroll: { vertTouchDrag: false },
    });

    // Candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      wickUpColor: '#26a69a',
    });

    // Volume series
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Set data
    const { candlestick, volume } = generateOHLCV();
    candlestickSeries.setData(candlestick);
    volumeSeries.setData(volume);

    chart.timeScale().fitContent();

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;

    // Resize observer
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    const cleanup = initChart();
    return cleanup;
  }, [initChart]);

  // ── Re-generate data on symbol/timeframe change ─────────────────
  const refreshData = useCallback(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) return;
    const { candlestick, volume } = generateOHLCV();
    candlestickSeriesRef.current.setData(candlestick);
    volumeSeriesRef.current.setData(volume);
    chartRef.current?.timeScale().fitContent();
  }, []);

  useEffect(() => {
    refreshData();
  }, [selectedSymbol, selectedTimeframe, refreshData]);

  return (
    <section className="glass-card overflow-hidden animate-slide-up">
      {/* ── Toolbar ── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border/40">
        {/* Left: Symbol selector + timeframes */}
        <div className="flex items-center gap-3">
          {/* Symbol dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowSymbolDropdown(!showSymbolDropdown)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-elevated hover:bg-surface-hover border border-border/50 transition-colors duration-200"
            >
              <span className="text-sm font-semibold text-text-primary">
                {selectedSymbol.label}
              </span>
              <ChevronDown
                size={14}
                className={`text-text-secondary transition-transform duration-200 ${
                  showSymbolDropdown ? 'rotate-180' : ''
                }`}
              />
            </button>

            {showSymbolDropdown && (
              <div className="absolute top-full left-0 mt-1 w-48 rounded-lg bg-surface-elevated border border-border shadow-elevated z-50 py-1 animate-fade-in">
                {SYMBOLS.map((sym) => (
                  <button
                    key={sym.value}
                    onClick={() => {
                      setSelectedSymbol(sym);
                      setShowSymbolDropdown(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-sm transition-colors duration-150 ${
                      selectedSymbol.value === sym.value
                        ? 'text-accent bg-accent-subtle'
                        : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
                    }`}
                  >
                    {sym.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="w-px h-5 bg-border/40" />

          {/* Timeframe buttons */}
          <div className="flex items-center gap-0.5">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all duration-200 ${
                  selectedTimeframe === tf
                    ? 'bg-accent text-white shadow-[0_0_10px_rgba(56,139,253,0.3)]'
                    : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1">
          <button
            onClick={refreshData}
            className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary hover:text-text-primary transition-colors"
            title="Refresh data"
          >
            <RefreshCw size={14} />
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary hover:text-text-primary transition-colors"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>

      {/* ── Chart container ── */}
      <div
        ref={chartContainerRef}
        className={`w-full ${isFullscreen ? 'h-[calc(100vh-200px)]' : 'h-[420px]'} transition-all duration-300`}
      />
    </section>
  );
}
