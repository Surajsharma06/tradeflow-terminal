import { useMemo } from 'react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';

// ── Generate mock sparkline data ──────────────────────────────────
function generateSparkline(trend, points = 24) {
  const data = [];
  let v = 100 + Math.random() * 20;
  for (let i = 0; i < points; i++) {
    const d = trend === 'up'
      ? Math.random() * 3 - 0.5
      : trend === 'down'
        ? Math.random() * 3 - 2.5
        : Math.random() * 4 - 2;
    v = Math.max(60, v + d);
    data.push({ v: +v.toFixed(2) });
  }
  return data;
}

// ── Mock market data ──────────────────────────────────────────────
const MARKETS = [
  { name: 'NIFTY 50',   price: '24,832.50', change: '+1.23%', changeVal: '+302.15', positive: true,  currency: '₹', flag: '🇮🇳' },
  { name: 'SENSEX',     price: '81,765.30', change: '+1.08%', changeVal: '+873.20', positive: true,  currency: '₹', flag: '🇮🇳' },
  { name: 'NIFTY BANK', price: '53,412.80', change: '-0.34%', changeVal: '-182.45', positive: false, currency: '₹', flag: '🇮🇳' },
  { name: 'S&P 500',    price: '5,942.18',  change: '+0.67%', changeVal: '+39.52',  positive: true,  currency: '$', flag: '🇺🇸' },
  { name: 'NASDAQ',     price: '19,218.45', change: '+1.12%', changeVal: '+213.40', positive: true,  currency: '$', flag: '🇺🇸' },
  { name: 'BTC/USDT',   price: '108,432',   change: '+2.34%', changeVal: '+2,481',  positive: true,  currency: '$', flag: '₿' },
];

// ── Market card ───────────────────────────────────────────────────
function MarketCard({ market }) {
  const sparkline = useMemo(
    () => generateSparkline(market.positive ? 'up' : 'down'),
    [market.positive]
  );

  const color = market.positive ? 'var(--color-positive)' : 'var(--color-negative)';
  const gradientId = `mkt-${market.name.replace(/[^a-z0-9]/gi, '')}`;

  return (
    <div
      className={`glass-card group relative overflow-hidden p-4 hover-lift cursor-default transition-all duration-300 ${
        market.positive
          ? 'hover:border-positive/30 hover:shadow-[0_0_24px_rgba(63,185,80,0.12)]'
          : 'hover:border-negative/30 hover:shadow-[0_0_24px_rgba(248,81,73,0.12)]'
      }`}
    >
      {/* Subtle corner glow */}
      <div
        className={`absolute -top-8 -right-8 w-24 h-24 rounded-full blur-2xl opacity-0 group-hover:opacity-30 transition-opacity duration-500 ${
          market.positive ? 'bg-positive' : 'bg-negative'
        }`}
      />

      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">{market.flag}</span>
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            {market.name}
          </span>
        </div>
        <div
          className={`flex items-center justify-center w-6 h-6 rounded-md ${
            market.positive ? 'bg-positive-subtle' : 'bg-negative-subtle'
          }`}
        >
          {market.positive ? (
            <TrendingUp size={13} className="text-positive" />
          ) : (
            <TrendingDown size={13} className="text-negative" />
          )}
        </div>
      </div>

      {/* Price */}
      <div className="font-tabular text-xl font-bold text-text-primary mb-1 tracking-tight">
        {market.currency}{market.price}
      </div>

      {/* Change row */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`font-tabular text-sm font-semibold ${
            market.positive ? 'text-positive' : 'text-negative'
          }`}
        >
          {market.change}
        </span>
        <span className="font-tabular text-xs text-text-tertiary">
          ({market.changeVal})
        </span>
      </div>

      {/* Sparkline */}
      <div className="h-10 -mx-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparkline} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#${gradientId})`}
              dot={false}
              isAnimationActive={true}
              animationDuration={1200}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
//  MARKET OVERVIEW COMPONENT
// ══════════════════════════════════════════════════════════════════
export default function MarketOverview() {
  return (
    <section className="animate-slide-up">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-1 h-5 rounded-full bg-accent" />
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          Market Overview
        </h2>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {MARKETS.map((m) => (
          <MarketCard key={m.name} market={m} />
        ))}
      </div>
    </section>
  );
}
