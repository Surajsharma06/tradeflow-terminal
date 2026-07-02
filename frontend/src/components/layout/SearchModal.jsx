import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, LayoutDashboard, Globe, BarChart3, FlaskConical,
  Wrench, Settings, TrendingUp, CornerDownLeft,
} from 'lucide-react';

// ── Searchable dataset: pages + market symbols ────────────────────
const PAGES = [
  { type: 'page', label: 'Dashboard',  to: '/',          icon: LayoutDashboard, hint: 'Market overview & signals' },
  { type: 'page', label: 'Forex',      to: '/forex',     icon: Globe,           hint: 'ICT/SMC forex intelligence' },
  { type: 'page', label: 'Analytics',  to: '/analytics', icon: BarChart3,       hint: 'Performance & equity curve' },
  { type: 'page', label: 'Backtest',   to: '/backtest',  icon: FlaskConical,    hint: 'Strategy backtesting' },
  { type: 'page', label: 'Tools',      to: '/tools',     icon: Wrench,          hint: 'Position size & charges' },
  { type: 'page', label: 'Settings',   to: '/settings',  icon: Settings,        hint: 'API keys & preferences' },
];

const SYMBOLS = [
  { type: 'symbol', label: 'NIFTY 50',   to: '/',      hint: 'NSE Index' },
  { type: 'symbol', label: 'SENSEX',     to: '/',      hint: 'BSE Index' },
  { type: 'symbol', label: 'NIFTY BANK', to: '/',      hint: 'NSE Bank Index' },
  { type: 'symbol', label: 'S&P 500',    to: '/',      hint: 'US Index' },
  { type: 'symbol', label: 'NASDAQ',     to: '/',      hint: 'US Tech Index' },
  { type: 'symbol', label: 'EUR/USD',    to: '/forex', hint: 'Forex Major' },
  { type: 'symbol', label: 'GBP/USD',    to: '/forex', hint: 'Forex Major' },
  { type: 'symbol', label: 'USD/JPY',    to: '/forex', hint: 'Forex Major' },
  { type: 'symbol', label: 'USD/CAD',    to: '/forex', hint: 'Forex Major' },
  { type: 'symbol', label: 'AUD/USD',    to: '/forex', hint: 'Forex Major' },
  { type: 'symbol', label: 'NZD/USD',    to: '/forex', hint: 'Forex Major' },
  { type: 'symbol', label: 'BTC/USDT',   to: '/',      hint: 'Crypto' },
  { type: 'symbol', label: 'ETH/USDT',   to: '/',      hint: 'Crypto' },
  { type: 'symbol', label: 'GOLD (XAU)', to: '/',      hint: 'Commodity' },
];

const ALL_ITEMS = [...PAGES, ...SYMBOLS];

export default function SearchModal({ open, onClose }) {
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const navigate = useNavigate();

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ALL_ITEMS.slice(0, 8);
    return ALL_ITEMS.filter(
      (item) =>
        item.label.toLowerCase().includes(q) ||
        item.hint.toLowerCase().includes(q)
    ).slice(0, 10);
  }, [query]);

  // Reset state each time the modal opens, then focus input.
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIdx(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => { setActiveIdx(0); }, [query]);

  const select = useCallback((item) => {
    if (!item) return;
    navigate(item.to);
    onClose();
  }, [navigate, onClose]);

  const onKeyDown = (e) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      select(results[activeIdx]);
    }
  };

  // Keep active row in view while arrowing through results.
  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-idx="${activeIdx}"]`)
      ?.scrollIntoView({ block: 'nearest' });
  }, [activeIdx]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[80]"
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Search"
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="fixed left-1/2 top-[15vh] -translate-x-1/2 w-[540px] max-w-[calc(100vw-24px)] rounded-xl border border-border bg-surface-elevated shadow-elevated z-[90] overflow-hidden"
          >
            {/* Input row */}
            <div className="flex items-center gap-2.5 px-4 h-12 border-b border-border/60">
              <Search size={15} className="text-text-tertiary flex-shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Search pages, symbols, pairs…"
                className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-tertiary outline-none"
                aria-label="Search input"
              />
              <kbd className="hidden sm:block text-[9px] font-semibold px-1.5 py-0.5 rounded border border-border text-text-tertiary">ESC</kbd>
            </div>

            {/* Results */}
            <div ref={listRef} className="max-h-[320px] overflow-y-auto py-1.5">
              {results.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-10 text-text-tertiary">
                  <Search size={20} />
                  <span className="text-xs">No results for “{query}”</span>
                  <span className="text-[10px] text-text-muted">Try a symbol, pair, or page name</span>
                </div>
              ) : (
                results.map((item, idx) => {
                  const Icon = item.icon ?? TrendingUp;
                  return (
                    <button
                      key={`${item.type}-${item.label}`}
                      data-idx={idx}
                      onClick={() => select(item)}
                      onMouseEnter={() => setActiveIdx(idx)}
                      className={`w-full flex items-center gap-3 px-4 py-2 text-left transition-colors cursor-pointer ${
                        idx === activeIdx ? 'bg-accent-subtle' : ''
                      }`}
                    >
                      <span className={`flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0 ${
                        item.type === 'page' ? 'bg-surface-hover text-text-secondary' : 'bg-accent-subtle text-accent'
                      }`}>
                        <Icon size={13} />
                      </span>
                      <span className="flex flex-col min-w-0 flex-1">
                        <span className="text-xs font-semibold text-text-primary">{item.label}</span>
                        <span className="text-[10px] text-text-tertiary">{item.hint}</span>
                      </span>
                      <span className="text-[9px] uppercase tracking-wider font-bold text-text-muted">
                        {item.type}
                      </span>
                      {idx === activeIdx && (
                        <CornerDownLeft size={12} className="text-text-tertiary" />
                      )}
                    </button>
                  );
                })
              )}
            </div>

            {/* Footer hints */}
            <div className="flex items-center gap-3 px-4 py-2 border-t border-border/60 text-[10px] text-text-tertiary">
              <span><kbd className="font-semibold">↑↓</kbd> navigate</span>
              <span><kbd className="font-semibold">↵</kbd> open</span>
              <span><kbd className="font-semibold">esc</kbd> close</span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
