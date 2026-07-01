import { useState, useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import useCurrencyStore from '../../stores/currencyStore';

const PERIODS = [
  { key: '1M', days: 30 },
  { key: '3M', days: 90 },
  { key: '6M', days: 180 },
  { key: 'ALL', days: 99999 },
];

function CustomTooltip({ active, payload }) {
  const { format } = useCurrencyStore();
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload ?? {};
  return (
    <div className="glass-card-elevated px-3 py-2.5 shadow-lg min-w-[180px]">
      <p className="text-[10px] text-text-secondary mb-1.5 font-medium">{d.dateLabel}</p>
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <span className="h-2 w-2 rounded-full bg-accent" />Portfolio
          </span>
          <span className="text-xs font-tabular font-semibold text-text-primary">
            {format(d.equity_usd, 2)}
          </span>
        </div>
        {d.drawdown_pct > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-secondary">Drawdown</span>
            <span className="text-[10px] font-tabular text-negative">-{d.drawdown_pct}%</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PerformanceChart({ equityCurve, startingCapital = 10_000, loading = false, className = '' }) {
  const [period, setPeriod] = useState('6M');
  const { format, symbol }  = useCurrencyStore();

  const allData = useMemo(() => {
    if (!equityCurve?.length) return [];
    return equityCurve
      .filter(p => p.date && p.date !== 'start')
      .map(p => ({
        date:          p.date,
        dateLabel:     p.date,
        equity_usd:    p.equity,
        drawdown_pct:  p.drawdown_pct ?? 0,
      }));
  }, [equityCurve]);

  const filteredData = useMemo(() => {
    if (!allData.length) return [];
    const cfg = PERIODS.find(p => p.key === period);
    const days = cfg?.days ?? 99999;
    return allData.slice(-days);
  }, [allData, period]);

  const startEq  = filteredData[0]?.equity_usd  ?? startingCapital;
  const endEq    = filteredData[filteredData.length - 1]?.equity_usd ?? startingCapital;
  const retPct   = startEq > 0 ? ((endEq - startEq) / startEq * 100).toFixed(2) : '0.00';
  const isProfit = Number(retPct) >= 0;

  const sym = symbol();

  return (
    <div className={`glass-card p-5 ${className}`}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-subtle">
            <TrendingUp className="h-4 w-4 text-accent" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Equity Curve</h3>
            <p className="text-xs text-text-secondary">Real 6-month SMC backtest · 5 forex pairs</p>
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-surface p-1">
          {PERIODS.map(({ key }) => (
            <button
              key={key}
              onClick={() => setPeriod(key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 cursor-pointer ${
                period === key ? 'bg-accent text-white shadow-sm' : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
              }`}
            >{key}</button>
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div className="flex flex-wrap gap-6 mb-4">
        <div>
          <span className="text-xs text-text-secondary">Capital</span>
          <p className="text-lg font-semibold font-tabular text-text-primary">{format(endEq, 2)}</p>
        </div>
        <div>
          <span className="text-xs text-text-secondary">Return</span>
          <p className={`text-lg font-semibold font-tabular ${isProfit ? 'text-profit' : 'text-loss'}`}>
            {isProfit ? '+' : ''}{retPct}%
          </p>
        </div>
        <div>
          <span className="text-xs text-text-secondary">Starting</span>
          <p className="text-lg font-semibold font-tabular text-text-secondary">{format(startingCapital, 0)}</p>
        </div>
      </div>

      <div className="h-[320px] w-full">
        {loading || !filteredData.length ? (
          <div className="flex items-center justify-center h-full text-text-muted text-sm">
            {loading ? 'Running backtest…' : 'No data yet'}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filteredData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="eqGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="var(--color-accent)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="dateLabel"
                stroke="var(--color-border)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
                tick={{ fill: 'var(--color-text-tertiary)' }}
              />
              <YAxis
                stroke="var(--color-border)"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                tick={{ fill: 'var(--color-text-tertiary)' }}
                tickFormatter={(v) => `${sym}${(v / 1000).toFixed(1)}K`}
                width={60}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="equity_usd"
                stroke="var(--color-accent)"
                strokeWidth={2}
                fill="url(#eqGradient)"
                dot={false}
                activeDot={{ r: 4, fill: 'var(--color-accent)', stroke: 'var(--color-bg)', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
