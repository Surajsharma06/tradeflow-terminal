import { useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  Play, Loader2, TrendingUp, Target, BarChart3, Shield, Activity, Zap,
  ChevronDown,
} from 'lucide-react';
import { format, subDays } from 'date-fns';

const STRATEGIES = [
  'Trend Following',
  'Mean Reversion',
  'Momentum',
  'Scalping',
  'Swing Trading',
  'Options Selling',
];

function generateBacktestResults(symbol, strategy, capital) {
  // Generate equity curve
  const days = 252; // 1 trading year
  const equityCurve = [];
  let equity = capital;

  for (let i = days; i >= 0; i--) {
    const date = subDays(new Date(), i);
    const dailyReturn = (Math.random() - 0.46) * 0.025;
    equity *= (1 + dailyReturn);
    equityCurve.push({
      date: format(date, 'yyyy-MM-dd'),
      dateLabel: format(date, 'dd MMM'),
      equity: Math.round(equity),
    });
  }

  const finalEquity = equityCurve[equityCurve.length - 1].equity;
  const totalReturn = ((finalEquity / capital - 1) * 100).toFixed(2);
  const cagr = (((finalEquity / capital) ** (1 / 1) - 1) * 100).toFixed(2);

  // Generate trade log
  const tradeLog = [];
  for (let i = 0; i < 20; i++) {
    const isWin = Math.random() > 0.42;
    const entry = 1800 + Math.random() * 800;
    const pnlPct = isWin ? Math.random() * 5 : -(Math.random() * 4);
    const exit = entry * (1 + pnlPct / 100);
    tradeLog.push({
      id: i + 1,
      date: format(subDays(new Date(), Math.floor(Math.random() * 252)), 'dd MMM yy'),
      symbol,
      side: Math.random() > 0.5 ? 'LONG' : 'SHORT',
      entry: entry.toFixed(2),
      exit: exit.toFixed(2),
      pnl: ((exit - entry) * 100).toFixed(0),
      pnlPct: pnlPct.toFixed(2),
      isWin,
    });
  }

  // Compute drawdown for max DD
  let peak = capital;
  let maxDD = 0;
  equityCurve.forEach(d => {
    if (d.equity > peak) peak = d.equity;
    const dd = ((d.equity - peak) / peak) * 100;
    if (dd < maxDD) maxDD = dd;
  });

  return {
    totalReturn,
    cagr,
    sharpe: (1.2 + Math.random() * 0.8).toFixed(2),
    sortino: (1.5 + Math.random() * 1.0).toFixed(2),
    maxDrawdown: maxDD.toFixed(2),
    winRate: (52 + Math.random() * 14).toFixed(1),
    profitFactor: (1.2 + Math.random() * 0.8).toFixed(2),
    totalTrades: 180 + Math.floor(Math.random() * 120),
    equityCurve,
    tradeLog,
    finalEquity,
  };
}

const EquityTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  return (
    <div className="glass-card-elevated px-3 py-2 shadow-lg">
      <p className="text-xs text-text-secondary">{data.date}</p>
      <p className="text-sm font-semibold font-mono font-tabular text-accent">
        ₹{data.equity.toLocaleString('en-IN')}
      </p>
    </div>
  );
};

export default function BacktestRunner({ className = '' }) {
  const [symbol, setSymbol] = useState('RELIANCE');
  const [strategy, setStrategy] = useState('Trend Following');
  const [capital, setCapital] = useState(500000);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [showTradeLog, setShowTradeLog] = useState(false);

  const handleRun = () => {
    setIsRunning(true);
    setResults(null);
    // Simulate backtest running
    setTimeout(() => {
      setResults(generateBacktestResults(symbol, strategy, capital));
      setIsRunning(false);
    }, 2000);
  };

  return (
    <div className={`glass-card p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-subtle">
          <Zap className="h-4.5 w-4.5 text-purple" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Backtest Runner</h3>
          <p className="text-xs text-text-secondary">Test strategy performance on historical data</p>
        </div>
      </div>

      {/* Input form */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">Stock Symbol</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="e.g. RELIANCE"
            className="w-full rounded-lg bg-surface border border-border px-3 py-2.5 text-sm font-mono text-text-primary
              focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all uppercase"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">Strategy</label>
          <div className="relative">
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full rounded-lg bg-surface border border-border px-3 py-2.5 text-sm text-text-primary
                focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all appearance-none cursor-pointer"
            >
              {STRATEGIES.map(s => (
                <option key={s} value={s} className="bg-surface-elevated">{s}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary pointer-events-none" />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">Initial Capital</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-sm">₹</span>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="w-full rounded-lg bg-surface border border-border px-3 py-2.5 pl-7 text-sm font-mono font-tabular text-text-primary
                focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all"
            />
          </div>
        </div>

        <div className="flex items-end">
          <button
            onClick={handleRun}
            disabled={isRunning}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-accent hover:bg-accent-hover text-white
              px-4 py-2.5 text-sm font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
              shadow-lg shadow-accent/20 hover:shadow-accent/30"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running Backtest...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run Backtest
              </>
            )}
          </button>
        </div>
      </div>

      {/* Loading animation */}
      {isRunning && (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="relative">
            <div className="w-16 h-16 rounded-full border-2 border-accent/20" />
            <div className="absolute inset-0 w-16 h-16 rounded-full border-2 border-transparent border-t-accent animate-spin" />
            <Activity className="absolute inset-0 m-auto h-6 w-6 text-accent" />
          </div>
          <p className="text-sm text-text-secondary mt-4 animate-pulse">
            Processing {symbol} with {strategy}...
          </p>
        </div>
      )}

      {/* Results */}
      {results && !isRunning && (
        <div className="space-y-5 animate-[fade-in_0.3s_ease-out]">
          {/* Metrics grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Total Return', value: `${results.totalReturn}%`, color: Number(results.totalReturn) >= 0 ? 'text-profit' : 'text-loss', icon: TrendingUp },
              { label: 'CAGR', value: `${results.cagr}%`, color: 'text-accent', icon: BarChart3 },
              { label: 'Sharpe Ratio', value: results.sharpe, color: Number(results.sharpe) >= 1.5 ? 'text-positive' : 'text-warning', icon: Target },
              { label: 'Sortino', value: results.sortino, color: 'text-purple', icon: Shield },
              { label: 'Max Drawdown', value: `${results.maxDrawdown}%`, color: 'text-loss', icon: TrendingUp },
              { label: 'Win Rate', value: `${results.winRate}%`, color: 'text-positive', icon: Target },
              { label: 'Profit Factor', value: results.profitFactor, color: 'text-gold', icon: BarChart3 },
              { label: 'Total Trades', value: results.totalTrades, color: 'text-text-primary', icon: Activity },
            ].map((metric) => (
              <div key={metric.label} className="rounded-lg bg-surface p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <metric.icon className={`h-3 w-3 ${metric.color}`} />
                  <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
                    {metric.label}
                  </span>
                </div>
                <p className={`text-base font-semibold font-mono font-tabular ${metric.color}`}>
                  {metric.value}
                </p>
              </div>
            ))}
          </div>

          {/* Equity Curve */}
          <div className="rounded-lg bg-surface p-4">
            <h4 className="text-xs font-semibold text-text-primary mb-3">Equity Curve</h4>
            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={results.equityCurve} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="btEquityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#bc8cff" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#bc8cff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" vertical={false} />
                  <XAxis dataKey="dateLabel" stroke="#484f58" fontSize={10} tickLine={false} axisLine={false} tick={{ fill: '#6e7681' }} interval="preserveStartEnd" />
                  <YAxis stroke="#484f58" fontSize={10} tickLine={false} axisLine={false} tick={{ fill: '#6e7681' }} tickFormatter={(v) => `₹${(v / 100000).toFixed(1)}L`} width={60} />
                  <Tooltip content={<EquityTooltip />} />
                  <Area type="monotone" dataKey="equity" stroke="#bc8cff" strokeWidth={2} fill="url(#btEquityGrad)" dot={false} activeDot={{ r: 3, fill: '#bc8cff', stroke: '#0d1117', strokeWidth: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Trade Log */}
          <div className="rounded-lg bg-surface p-4">
            <button
              onClick={() => setShowTradeLog(!showTradeLog)}
              className="w-full flex items-center justify-between text-xs font-semibold text-text-primary hover:text-accent transition-colors"
            >
              <span>Trade Log ({results.tradeLog.length} recent trades)</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${showTradeLog ? 'rotate-180' : ''}`} />
            </button>

            {showTradeLog && (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[600px]">
                  <thead>
                    <tr className="border-b border-border">
                      {['#', 'Date', 'Symbol', 'Side', 'Entry', 'Exit', 'P&L', 'P&L %'].map(h => (
                        <th key={h} className="py-2 px-2 text-[10px] uppercase tracking-wider font-semibold text-text-tertiary text-left">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.tradeLog.map((trade) => (
                      <tr key={trade.id} className="border-b border-border/30 hover:bg-surface-hover/50 transition-colors">
                        <td className="py-2 px-2 text-xs text-text-tertiary">{trade.id}</td>
                        <td className="py-2 px-2 text-xs text-text-secondary">{trade.date}</td>
                        <td className="py-2 px-2 text-xs font-medium text-text-primary">{trade.symbol}</td>
                        <td className="py-2 px-2">
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                            trade.side === 'LONG' ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'
                          }`}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-xs font-mono font-tabular text-text-primary">₹{trade.entry}</td>
                        <td className="py-2 px-2 text-xs font-mono font-tabular text-text-primary">₹{trade.exit}</td>
                        <td className={`py-2 px-2 text-xs font-mono font-tabular font-semibold ${trade.isWin ? 'text-positive' : 'text-negative'}`}>
                          {trade.isWin ? '+' : ''}₹{Number(trade.pnl).toLocaleString('en-IN')}
                        </td>
                        <td className={`py-2 px-2 text-xs font-mono font-tabular ${trade.isWin ? 'text-positive' : 'text-negative'}`}>
                          {trade.isWin ? '+' : ''}{trade.pnlPct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
