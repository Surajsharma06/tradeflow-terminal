import { useState, useEffect, useRef } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Wifi,
  Clock,
  Bell,
  Search,
  Sun,
  Moon,
  Menu,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';
import useThemeStore from '../../stores/themeStore';
import useCurrencyStore from '../../stores/currencyStore';
import useNotificationStore from '../../stores/notificationStore';
import NotificationsMenu from './NotificationsMenu';
import SearchModal from './SearchModal';

// ── Mock ticker data ──────────────────────────────────────────────
const generateSparklineData = (trend = 'up', points = 20) => {
  const data = [];
  let value = 100 + Math.random() * 50;
  for (let i = 0; i < points; i++) {
    const delta = trend === 'up'
      ? Math.random() * 4 - 1
      : trend === 'down'
        ? Math.random() * 4 - 3
        : Math.random() * 6 - 3;
    value = Math.max(50, value + delta);
    data.push({ v: value });
  }
  return data;
};

// Prices are numeric and tagged with their native currency so the
// currency switcher can convert them into whatever the user selects.
const TICKER_DATA = [
  { symbol: 'NIFTY 50',   price: 24832.50,  native: 'INR', decimals: 2, change: '+1.23%', positive: true,  sparkline: generateSparklineData('up') },
  { symbol: 'SENSEX',     price: 81765.30,  native: 'INR', decimals: 2, change: '+1.08%', positive: true,  sparkline: generateSparklineData('up') },
  { symbol: 'NIFTY BANK', price: 53412.80,  native: 'INR', decimals: 2, change: '-0.34%', positive: false, sparkline: generateSparklineData('down') },
  { symbol: 'S&P 500',    price: 5942.18,   native: 'USD', decimals: 2, change: '+0.67%', positive: true,  sparkline: generateSparklineData('up') },
  { symbol: 'NASDAQ',     price: 19218.45,  native: 'USD', decimals: 2, change: '+1.12%', positive: true,  sparkline: generateSparklineData('up') },
  { symbol: 'BTC/USDT',   price: 108432.50, native: 'USD', decimals: 0, change: '+2.34%', positive: true,  sparkline: generateSparklineData('up') },
  { symbol: 'ETH/USDT',   price: 3892.15,   native: 'USD', decimals: 2, change: '-0.87%', positive: false, sparkline: generateSparklineData('down') },
  { symbol: 'GOLD',       price: 2718.40,   native: 'USD', decimals: 2, change: '+0.42%', positive: true,  sparkline: generateSparklineData('up') },
];

const VIX_DATA = [
  { label: 'INDIA VIX', value: '13.42', change: '-2.1%', positive: false },
  { label: 'US VIX',    value: '14.87', change: '+1.8%', positive: true  },
];

const MARKET_STATUS = [
  { market: 'NSE',    open: true  },
  { market: 'NYSE',   open: false },
  { market: 'CRYPTO', open: true  },
];

const REGIME = { label: 'BULL', type: 'bull' };

// ── Mini sparkline ────────────────────────────────────────────────
function MiniSparkline({ data, positive, width = 56, height = 20 }) {
  const color = positive ? 'var(--color-positive)' : 'var(--color-negative)';
  return (
    <div style={{ width, height }} className="flex-shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
          <defs>
            <linearGradient id={`spark-${positive ? 'g' : 'r'}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0}   />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5}
            fill={`url(#spark-${positive ? 'g' : 'r'})`} dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function TickerItem({ item }) {
  // Subscribing to `currency` ensures re-render when the user switches;
  // formatFrom converts from the asset's native currency.
  useCurrencyStore((s) => s.currency);
  const formatFrom = useCurrencyStore((s) => s.formatFrom);
  return (
    <div className="flex items-center gap-3 px-5 py-1.5 border-r border-border/40 flex-shrink-0 group cursor-default">
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wider text-text-secondary font-medium group-hover:text-text-primary transition-colors">
          {item.symbol}
        </span>
        <div className="flex items-center gap-2">
          <span className="font-tabular text-sm font-semibold text-text-primary">
            {formatFrom(item.price, item.native, item.decimals)}
          </span>
          <span className={`font-tabular text-xs font-medium ${item.positive ? 'text-positive' : 'text-negative'}`}>
            {item.change}
          </span>
        </div>
      </div>
      <MiniSparkline data={item.sparkline} positive={item.positive} />
    </div>
  );
}

function MarketBadge({ market, open }) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-surface-elevated/60">
      <span className={open ? 'status-dot status-dot-live' : 'status-dot status-dot-closed'} />
      <span className="text-[10px] font-semibold tracking-wider text-text-secondary uppercase">{market}</span>
      <span className={`text-[9px] font-bold uppercase tracking-wider ${open ? 'text-positive' : 'text-text-muted'}`}>
        {open ? 'OPEN' : 'CLOSED'}
      </span>
    </div>
  );
}

function RegimeBadge({ regime }) {
  const colors = {
    bull:     'bg-positive-subtle text-positive border-positive/30',
    bear:     'bg-negative-subtle text-negative border-negative/30',
    sideways: 'bg-warning-subtle text-warning border-warning/30',
  };
  const icons = {
    bull:     <TrendingUp size={12} />,
    bear:     <TrendingDown size={12} />,
    sideways: <Minus size={12} />,
  };
  return (
    <div className={`flex items-center gap-1 px-2.5 py-1 rounded-md border text-[10px] font-bold uppercase tracking-wider ${colors[regime.type]}`}>
      {icons[regime.type]}
      {regime.label}
    </div>
  );
}

function VixDisplay({ data }) {
  return (
    <div className="flex items-center gap-1.5 px-2">
      <Activity size={12} className="text-accent" />
      <span className="text-[10px] text-text-tertiary font-medium">{data.label}</span>
      <span className="font-tabular text-xs font-semibold text-text-primary">{data.value}</span>
      <span className={`font-tabular text-[10px] ${data.positive ? 'text-negative' : 'text-positive'}`}>
        {data.change}
      </span>
    </div>
  );
}

function TimeDisplay() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="hidden sm:flex items-center gap-1.5 px-2 text-text-secondary">
      <Clock size={12} />
      <span className="font-tabular text-xs font-medium">
        {time.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
      </span>
      <span className="text-[9px] text-text-tertiary">IST</span>
    </div>
  );
}

// ── Currency Switcher ─────────────────────────────────────────────
function CurrencySwitcher() {
  const { currency, setCurrency } = useCurrencyStore();
  return (
    <div
      role="group"
      aria-label="Display currency"
      className="flex items-center gap-0.5 rounded-lg bg-surface p-0.5 border border-border/50"
    >
      {['USD', 'INR', 'CAD'].map(c => (
        <motion.button
          key={c}
          whileTap={{ scale: 0.94 }}
          onClick={() => setCurrency(c)}
          aria-pressed={currency === c}
          className={`px-2 py-1 text-[10px] font-bold rounded-md transition-all cursor-pointer ${
            currency === c
              ? 'bg-accent text-white shadow-sm'
              : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
          }`}
        >{c}</motion.button>
      ))}
    </div>
  );
}

// ── Theme Toggle ──────────────────────────────────────────────────
function ThemeToggle() {
  const { theme, toggle } = useThemeStore();
  return (
    <motion.button
      whileTap={{ scale: 0.9 }}
      onClick={toggle}
      className="p-1.5 rounded-md hover:bg-surface-hover transition-colors text-text-secondary hover:text-text-primary cursor-pointer"
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
    </motion.button>
  );
}

// ══════════════════════════════════════════════════════════════════
//  HEADER COMPONENT
// ══════════════════════════════════════════════════════════════════
export default function Header() {
  const tickerRef = useRef(null);
  const bellRef = useRef(null);
  const [isPaused, setIsPaused] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const { theme, init } = useThemeStore();
  const notifications = useNotificationStore((s) => s.notifications);
  const readIds = useNotificationStore((s) => s.readIds);
  const unread = notifications.filter((n) => !readIds.includes(n.id)).length;

  useEffect(() => { init(theme); }, []);

  // Global Cmd+K / Ctrl+K opens search
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const tickerItems = [...TICKER_DATA, ...TICKER_DATA];

  return (
    <header className="w-full bg-bg-alt/80 backdrop-blur-xl border-b border-border/60 z-50 select-none">
      {/* ── Top info bar ── */}
      <div className="flex items-center justify-between px-3 h-12 md:h-9 border-b border-border/30">
        {/* Left: Mobile hamburger + Market statuses */}
        <div className="flex items-center gap-2">
          {/* Mobile hamburger — 44x44 minimum tap target */}
          <motion.button
            whileTap={{ scale: 0.9 }}
            className="md:hidden flex items-center justify-center min-w-[44px] min-h-[44px] -ml-2 rounded-md hover:bg-surface-hover active:bg-surface-active transition-colors text-text-primary cursor-pointer"
            onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
            aria-label="Open navigation menu"
          >
            <Menu size={22} />
          </motion.button>
          <div className="hidden sm:flex items-center gap-2">
            {MARKET_STATUS.map((m) => (
              <MarketBadge key={m.market} market={m.market} open={m.open} />
            ))}
            <div className="w-px h-4 bg-border/40 mx-1" />
            <RegimeBadge regime={REGIME} />
          </div>
        </div>

        {/* Center: VIX (hidden on mobile) */}
        <div className="hidden md:flex items-center gap-3">
          {VIX_DATA.map((v) => <VixDisplay key={v.label} data={v} />)}
        </div>

        {/* Right: Currency + Theme + Time + Alerts */}
        <div className="flex items-center gap-1.5">
          <CurrencySwitcher />
          <div className="hidden sm:block w-px h-4 bg-border/40 mx-0.5" />
          <TimeDisplay />
          <div className="w-px h-4 bg-border/40 mx-0.5" />
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={() => setSearchOpen(true)}
            className="p-1.5 rounded-md hover:bg-surface-hover transition-colors text-text-secondary hover:text-text-primary cursor-pointer"
            aria-label="Search (Cmd+K)"
            title="Search (⌘K)"
          >
            <Search size={14} />
          </motion.button>

          {/* Notification bell + dropdown */}
          <div className="relative">
            <motion.button
              ref={bellRef}
              whileTap={{ scale: 0.9 }}
              onClick={() => setNotifOpen((o) => !o)}
              className="p-1.5 rounded-md hover:bg-surface-hover transition-colors text-text-secondary hover:text-text-primary relative cursor-pointer"
              aria-label={`Notifications${unread ? ` (${unread} unread)` : ''}`}
              aria-expanded={notifOpen}
            >
              <Bell size={14} />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] px-0.5 flex items-center justify-center rounded-full bg-negative text-white text-[8px] font-bold leading-none">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </motion.button>
            <NotificationsMenu
              open={notifOpen}
              onClose={() => setNotifOpen(false)}
              anchorRef={bellRef}
            />
          </div>

          <ThemeToggle />
          <div className="hidden sm:flex items-center gap-1 px-2 py-1 rounded-md bg-positive-subtle/60">
            <Wifi size={11} className="text-positive" />
            <span className="text-[10px] font-semibold text-positive">LIVE</span>
          </div>
        </div>
      </div>

      {/* ── Scrolling ticker tape ── */}
      <div
        className="relative h-10 overflow-hidden"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-bg-alt/80 to-transparent z-10 pointer-events-none" />
        <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-bg-alt/80 to-transparent z-10 pointer-events-none" />
        <div
          ref={tickerRef}
          className="flex items-center h-full ticker-tape"
          style={{ animationPlayState: isPaused ? 'paused' : 'running' }}
        >
          {tickerItems.map((item, idx) => (
            <TickerItem key={`${item.symbol}-${idx}`} item={item} />
          ))}
        </div>
      </div>

      {/* ── Search modal (portal-level) ── */}
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
    </header>
  );
}
