import { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, Target } from 'lucide-react';

const STRATEGIES = [
  {
    name: 'Trend Following',
    totalTrades: 234,
    winRate: 58.5,
    avgWin: 4250,
    avgLoss: 2890,
    profitFactor: 1.72,
    totalPnL: 285400,
    sharpe: 1.85,
    color: '#388bfd',
  },
  {
    name: 'Mean Reversion',
    totalTrades: 189,
    winRate: 64.2,
    avgWin: 3120,
    avgLoss: 3450,
    profitFactor: 1.35,
    totalPnL: 142800,
    sharpe: 1.22,
    color: '#bc8cff',
  },
  {
    name: 'Momentum',
    totalTrades: 312,
    winRate: 52.1,
    avgWin: 5680,
    avgLoss: 3200,
    profitFactor: 1.55,
    totalPnL: 198500,
    sharpe: 1.48,
    color: '#3fb950',
  },
  {
    name: 'Scalping',
    totalTrades: 1245,
    winRate: 61.8,
    avgWin: 890,
    avgLoss: 720,
    profitFactor: 1.42,
    totalPnL: 175200,
    sharpe: 1.15,
    color: '#e3b341',
  },
  {
    name: 'Swing Trading',
    totalTrades: 87,
    winRate: 55.2,
    avgWin: 12400,
    avgLoss: 8900,
    profitFactor: 1.38,
    totalPnL: 124600,
    sharpe: 0.98,
    color: '#f85149',
  },
  {
    name: 'Options',
    totalTrades: 156,
    winRate: 48.7,
    avgWin: 8900,
    avgLoss: 4200,
    profitFactor: 1.18,
    totalPnL: -32400,
    sharpe: 0.45,
    color: '#58a6ff',
  },
];

const COLUMNS = [
  { key: 'name', label: 'Strategy', align: 'left', sortable: true },
  { key: 'totalTrades', label: 'Trades', align: 'right', sortable: true },
  { key: 'winRate', label: 'Win Rate', align: 'right', sortable: true, isBar: true },
  { key: 'avgWin', label: 'Avg Win', align: 'right', sortable: true, isCurrency: true },
  { key: 'avgLoss', label: 'Avg Loss', align: 'right', sortable: true, isCurrency: true },
  { key: 'profitFactor', label: 'PF', align: 'right', sortable: true },
  { key: 'totalPnL', label: 'Total P&L', align: 'right', sortable: true, isCurrency: true, isPnL: true },
  { key: 'sharpe', label: 'Sharpe', align: 'right', sortable: true },
];

export default function StrategyBreakdown({ className = '' }) {
  const [sortKey, setSortKey] = useState('totalPnL');
  const [sortDir, setSortDir] = useState('desc');

  const sortedStrategies = useMemo(() => {
    return [...STRATEGIES].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (typeof aVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
    });
  }, [sortKey, sortDir]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const maxWinRate = Math.max(...STRATEGIES.map(s => s.winRate));

  return (
    <div className={`glass-card p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold-subtle">
          <Target className="h-4.5 w-4.5 text-gold" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Strategy Breakdown</h3>
          <p className="text-xs text-text-secondary">Performance by trading strategy</p>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto -mx-5 px-5">
        <table className="w-full min-w-[700px]">
          <thead>
            <tr className="border-b border-border">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`py-3 px-3 text-[10px] uppercase tracking-wider font-semibold text-text-tertiary
                    ${col.align === 'left' ? 'text-left' : 'text-right'}
                    ${col.sortable ? 'cursor-pointer select-none hover:text-text-secondary transition-colors' : ''}
                  `}
                  onClick={() => col.sortable && handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {col.sortable && sortKey === col.key && (
                      sortDir === 'asc'
                        ? <ChevronUp className="h-3 w-3 text-accent" />
                        : <ChevronDown className="h-3 w-3 text-accent" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedStrategies.map((strategy) => (
              <tr
                key={strategy.name}
                className="border-b border-border/50 hover:bg-surface-hover/50 transition-colors group"
              >
                {/* Strategy name */}
                <td className="py-3 px-3">
                  <div className="flex items-center gap-2.5">
                    <div
                      className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: strategy.color }}
                    />
                    <span className="text-sm font-medium text-text-primary group-hover:text-accent transition-colors">
                      {strategy.name}
                    </span>
                  </div>
                </td>

                {/* Total trades */}
                <td className="py-3 px-3 text-right">
                  <span className="text-sm font-mono font-tabular text-text-secondary">
                    {strategy.totalTrades.toLocaleString()}
                  </span>
                </td>

                {/* Win rate with bar */}
                <td className="py-3 px-3 text-right">
                  <div className="flex items-center gap-2 justify-end">
                    <div className="w-16 h-1.5 rounded-full bg-surface overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${(strategy.winRate / maxWinRate) * 100}%`,
                          backgroundColor: strategy.winRate >= 55 ? '#3fb950' : strategy.winRate >= 50 ? '#d29922' : '#f85149',
                        }}
                      />
                    </div>
                    <span className={`text-sm font-mono font-tabular font-medium ${
                      strategy.winRate >= 55 ? 'text-positive' : strategy.winRate >= 50 ? 'text-warning' : 'text-negative'
                    }`}>
                      {strategy.winRate}%
                    </span>
                  </div>
                </td>

                {/* Avg Win */}
                <td className="py-3 px-3 text-right">
                  <span className="text-sm font-mono font-tabular text-positive">
                    ₹{strategy.avgWin.toLocaleString('en-IN')}
                  </span>
                </td>

                {/* Avg Loss */}
                <td className="py-3 px-3 text-right">
                  <span className="text-sm font-mono font-tabular text-negative">
                    ₹{strategy.avgLoss.toLocaleString('en-IN')}
                  </span>
                </td>

                {/* Profit Factor */}
                <td className="py-3 px-3 text-right">
                  <span className={`text-sm font-mono font-tabular font-medium ${
                    strategy.profitFactor >= 1.5 ? 'text-positive' : strategy.profitFactor >= 1 ? 'text-warning' : 'text-negative'
                  }`}>
                    {strategy.profitFactor.toFixed(2)}
                  </span>
                </td>

                {/* Total PnL */}
                <td className="py-3 px-3 text-right">
                  <span className={`text-sm font-semibold font-mono font-tabular ${
                    strategy.totalPnL >= 0 ? 'text-profit' : 'text-loss'
                  }`}>
                    {strategy.totalPnL >= 0 ? '+' : '-'}₹{Math.abs(strategy.totalPnL).toLocaleString('en-IN')}
                  </span>
                </td>

                {/* Sharpe */}
                <td className="py-3 px-3 text-right">
                  <span className={`inline-flex items-center justify-center min-w-[42px] rounded-md px-2 py-0.5 text-xs font-mono font-tabular font-medium ${
                    strategy.sharpe >= 1.5 ? 'bg-positive-subtle text-positive' :
                    strategy.sharpe >= 1 ? 'bg-warning-subtle text-warning' :
                    'bg-negative-subtle text-negative'
                  }`}>
                    {strategy.sharpe.toFixed(2)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary footer */}
      <div className="mt-4 pt-4 border-t border-border flex flex-wrap items-center gap-6">
        <div>
          <span className="text-[10px] uppercase tracking-wider text-text-tertiary">Total P&L</span>
          <p className={`text-base font-semibold font-mono font-tabular ${
            STRATEGIES.reduce((s, st) => s + st.totalPnL, 0) >= 0 ? 'text-profit' : 'text-loss'
          }`}>
            {STRATEGIES.reduce((s, st) => s + st.totalPnL, 0) >= 0 ? '+' : '-'}₹{
              Math.abs(STRATEGIES.reduce((s, st) => s + st.totalPnL, 0)).toLocaleString('en-IN')
            }
          </p>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-text-tertiary">Total Trades</span>
          <p className="text-base font-semibold font-mono font-tabular text-text-primary">
            {STRATEGIES.reduce((s, st) => s + st.totalTrades, 0).toLocaleString()}
          </p>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-text-tertiary">Best Strategy</span>
          <p className="text-base font-semibold text-accent">
            {STRATEGIES.reduce((best, st) => st.totalPnL > best.totalPnL ? st : best).name}
          </p>
        </div>
      </div>
    </div>
  );
}
