import {
  ArrowUpRight,
  ArrowDownRight,
  Crosshair,
  Zap,
  Clock,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

// ── Mock signal data ──────────────────────────────────────────────
const SIGNALS = [
  {
    time: '10:32:15',
    symbol: 'RELIANCE',
    direction: 'BUY',
    strategy: 'Momentum Breakout',
    score: 92,
    entry: '₹2,842.50',
    sl: '₹2,815.00',
    target: '₹2,910.00',
    rr: '2.45',
    status: 'active',
  },
  {
    time: '10:28:45',
    symbol: 'TCS',
    direction: 'SELL',
    strategy: 'Mean Reversion',
    score: 87,
    entry: '₹3,654.00',
    sl: '₹3,690.00',
    target: '₹3,585.00',
    rr: '1.92',
    status: 'active',
  },
  {
    time: '10:15:30',
    symbol: 'HDFCBANK',
    direction: 'BUY',
    strategy: 'VWAP Bounce',
    score: 84,
    entry: '₹1,672.30',
    sl: '₹1,658.00',
    target: '₹1,705.00',
    rr: '2.28',
    status: 'triggered',
  },
  {
    time: '09:58:12',
    symbol: 'INFY',
    direction: 'BUY',
    strategy: 'Breakout Retest',
    score: 81,
    entry: '₹1,542.00',
    sl: '₹1,528.00',
    target: '₹1,580.00',
    rr: '2.71',
    status: 'active',
  },
  {
    time: '09:45:00',
    symbol: 'BAJFINANCE',
    direction: 'SELL',
    strategy: 'RSI Divergence',
    score: 78,
    entry: '₹7,125.00',
    sl: '₹7,180.00',
    target: '₹6,990.00',
    rr: '2.45',
    status: 'pending',
  },
  {
    time: '09:32:20',
    symbol: 'SBIN',
    direction: 'BUY',
    strategy: 'Volume Spike',
    score: 76,
    entry: '₹842.50',
    sl: '₹832.00',
    target: '₹868.00',
    rr: '2.43',
    status: 'active',
  },
  {
    time: '09:20:05',
    symbol: 'ITC',
    direction: 'BUY',
    strategy: 'Golden Cross',
    score: 74,
    entry: '₹465.80',
    sl: '₹458.00',
    target: '₹482.00',
    rr: '2.08',
    status: 'triggered',
  },
];

// Only show signals > 72 as per requirements
const filteredSignals = SIGNALS.filter((s) => s.score > 72);

// ── Score bar ─────────────────────────────────────────────────────
function ScoreBar({ score }) {
  const getBarColor = (score) => {
    if (score >= 85) return 'from-positive to-positive-strong';
    if (score >= 72) return 'from-warning to-positive';
    return 'from-negative to-warning';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-surface-active overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${getBarColor(score)} transition-all duration-700`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="font-tabular text-xs font-bold text-text-primary">{score}</span>
    </div>
  );
}

// ── Direction badge ───────────────────────────────────────────────
function DirectionBadge({ direction }) {
  const isBuy = direction === 'BUY';
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
        isBuy
          ? 'bg-positive-subtle text-positive border border-positive/20'
          : 'bg-negative-subtle text-negative border border-negative/20'
      }`}
    >
      {isBuy ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
      {direction}
    </span>
  );
}

// ── Status badge ──────────────────────────────────────────────────
function StatusBadge({ status }) {
  const config = {
    active: {
      icon: <Zap size={10} />,
      text: 'Active',
      classes: 'text-accent bg-accent-subtle',
    },
    triggered: {
      icon: <CheckCircle2 size={10} />,
      text: 'Triggered',
      classes: 'text-positive bg-positive-subtle',
    },
    pending: {
      icon: <Clock size={10} />,
      text: 'Pending',
      classes: 'text-warning bg-warning-subtle',
    },
    expired: {
      icon: <AlertCircle size={10} />,
      text: 'Expired',
      classes: 'text-text-muted bg-surface-active',
    },
  };

  const c = config[status] || config.active;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide ${c.classes}`}>
      {c.icon}
      {c.text}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════
//  SIGNAL TABLE COMPONENT
// ══════════════════════════════════════════════════════════════════
export default function SignalTable() {
  return (
    <section className="glass-card overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <div className="flex items-center gap-2">
          <Crosshair size={16} className="text-accent" />
          <h3 className="text-sm font-semibold text-text-primary">Active Signals</h3>
          <span className="flex items-center justify-center px-1.5 py-0.5 rounded-md bg-accent-subtle text-[10px] font-bold text-accent">
            {filteredSignals.length}
          </span>
        </div>
        <span className="text-[10px] text-text-tertiary uppercase tracking-wider">
          Score threshold: 72+
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/30">
              {['Time', 'Symbol', 'Direction', 'Strategy', 'Score', 'Entry', 'SL', 'Target', 'RR', 'Status'].map(
                (col) => (
                  <th
                    key={col}
                    className="px-4 py-2.5 text-[10px] font-semibold text-text-tertiary uppercase tracking-wider text-left whitespace-nowrap"
                  >
                    {col}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {filteredSignals.map((signal, idx) => (
              <tr
                key={idx}
                className="border-b border-border/20 hover:bg-surface-hover/50 transition-colors duration-150 group"
              >
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-text-secondary font-mono">
                    {signal.time}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs font-semibold text-text-primary group-hover:text-accent transition-colors">
                    {signal.symbol}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <DirectionBadge direction={signal.direction} />
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs text-text-secondary">{signal.strategy}</span>
                </td>
                <td className="px-4 py-3">
                  <ScoreBar score={signal.score} />
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-text-primary font-medium">
                    {signal.entry}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-negative/80">{signal.sl}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs text-positive/80">{signal.target}</span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-tabular text-xs font-bold text-accent">{signal.rr}</span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={signal.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
