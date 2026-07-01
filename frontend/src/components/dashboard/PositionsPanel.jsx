import { useMemo } from 'react';
import {
  Briefcase,
  ArrowUpRight,
  ArrowDownRight,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';

// ── Generate tiny sparkline ───────────────────────────────────────
function tinySparkline(trend, n = 16) {
  const d = [];
  let v = 100;
  for (let i = 0; i < n; i++) {
    v += trend === 'up' ? Math.random() * 3 - 0.5 : Math.random() * 3 - 2.5;
    d.push({ v: +v.toFixed(2) });
  }
  return d;
}

// ── Mock positions ────────────────────────────────────────────────
const POSITIONS = [
  {
    symbol: 'RELIANCE',
    type: 'LONG',
    entry: 2842.50,
    current: 2878.30,
    qty: 50,
    sl: 2815.00,
    target: 2910.00,
  },
  {
    symbol: 'TCS',
    type: 'SHORT',
    entry: 3654.00,
    current: 3628.40,
    qty: 30,
    sl: 3690.00,
    target: 3585.00,
  },
  {
    symbol: 'HDFCBANK',
    type: 'LONG',
    entry: 1672.30,
    current: 1665.80,
    qty: 100,
    sl: 1658.00,
    target: 1705.00,
  },
  {
    symbol: 'INFY',
    type: 'LONG',
    entry: 1542.00,
    current: 1568.50,
    qty: 75,
    sl: 1528.00,
    target: 1580.00,
  },
];

// ── Compute PnL ───────────────────────────────────────────────────
function computePosition(pos) {
  const multiplier = pos.type === 'SHORT' ? -1 : 1;
  const pnlPerShare = (pos.current - pos.entry) * multiplier;
  const pnlAbs = pnlPerShare * pos.qty;
  const pnlPct = (pnlPerShare / pos.entry) * 100;
  const positive = pnlAbs >= 0;
  return { ...pos, pnlAbs, pnlPct, positive, sparkline: tinySparkline(positive ? 'up' : 'down') };
}

// ── Inline sparkline ──────────────────────────────────────────────
function InlineSparkline({ data, positive }) {
  const color = positive ? 'var(--color-positive)' : 'var(--color-negative)';
  return (
    <div className="w-12 h-5 flex-shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 1, right: 0, left: 0, bottom: 1 }}>
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1}
            fill="transparent"
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Type badge ────────────────────────────────────────────────────
function TypeBadge({ type }) {
  const isLong = type === 'LONG';
  return (
    <span
      className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
        isLong
          ? 'bg-positive-subtle text-positive'
          : 'bg-negative-subtle text-negative'
      }`}
    >
      {isLong ? <ArrowUpRight size={9} /> : <ArrowDownRight size={9} />}
      {type}
    </span>
  );
}

// ── Format currency ───────────────────────────────────────────────
const fmt = (n) => '₹' + Math.abs(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtPct = (n) => (n >= 0 ? '+' : '') + n.toFixed(2) + '%';

// ══════════════════════════════════════════════════════════════════
//  POSITIONS PANEL COMPONENT
// ══════════════════════════════════════════════════════════════════
export default function PositionsPanel() {
  const positions = useMemo(() => POSITIONS.map(computePosition), []);
  const totalPnl = useMemo(() => positions.reduce((sum, p) => sum + p.pnlAbs, 0), [positions]);
  const totalPositive = totalPnl >= 0;

  return (
    <section className="glass-card overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <div className="flex items-center gap-2">
          <Briefcase size={16} className="text-purple" />
          <h3 className="text-sm font-semibold text-text-primary">Open Positions</h3>
          <span className="flex items-center justify-center px-1.5 py-0.5 rounded-md bg-purple-subtle text-[10px] font-bold text-purple">
            {positions.length}
          </span>
        </div>
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md ${totalPositive ? 'bg-positive-subtle' : 'bg-negative-subtle'}`}>
          {totalPositive ? (
            <TrendingUp size={12} className="text-positive" />
          ) : (
            <TrendingDown size={12} className="text-negative" />
          )}
          <span className={`font-tabular text-xs font-bold ${totalPositive ? 'text-positive' : 'text-negative'}`}>
            {totalPnl >= 0 ? '+' : '-'}{fmt(totalPnl)}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/30">
              {['Symbol', 'Type', 'Entry', 'Current', 'Qty', 'P&L (₹)', 'P&L (%)', 'SL', 'Target', ''].map(
                (col) => (
                  <th
                    key={col || 'spark'}
                    className="px-4 py-2.5 text-[10px] font-semibold text-text-tertiary uppercase tracking-wider text-left whitespace-nowrap"
                  >
                    {col}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {positions.map((pos) => (
              <tr
                key={pos.symbol}
                className="border-b border-border/20 hover:bg-surface-hover/50 transition-colors duration-150 group"
              >
                <td className="px-4 py-3">
                  <span className="text-xs font-semibold text-text-primary group-hover:text-accent transition-colors">
                    {pos.symbol}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <TypeBadge type={pos.type} />
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-text-secondary">₹{pos.entry.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-text-primary font-medium">₹{pos.current.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-text-secondary">{pos.qty}</span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`font-tabular text-xs font-bold ${
                      pos.positive ? 'text-profit' : 'text-loss'
                    }`}
                  >
                    {pos.pnlAbs >= 0 ? '+' : '-'}{fmt(pos.pnlAbs)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`font-tabular text-xs font-semibold px-1.5 py-0.5 rounded ${
                      pos.positive
                        ? 'text-positive bg-positive-subtle/50'
                        : 'text-negative bg-negative-subtle/50'
                    }`}
                  >
                    {fmtPct(pos.pnlPct)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-negative/70">₹{pos.sl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-positive/70">₹{pos.target.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </td>
                <td className="px-4 py-3">
                  <InlineSparkline data={pos.sparkline} positive={pos.positive} />
                </td>
              </tr>
            ))}
          </tbody>

          {/* Summary row */}
          <tfoot>
            <tr className="bg-surface-elevated/40">
              <td colSpan={5} className="px-4 py-3">
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                  Total P&L
                </span>
              </td>
              <td className="px-4 py-3">
                <span
                  className={`font-tabular text-sm font-bold ${
                    totalPositive ? 'text-profit' : 'text-loss'
                  }`}
                >
                  {totalPnl >= 0 ? '+' : '-'}{fmt(totalPnl)}
                </span>
              </td>
              <td colSpan={4} />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
