import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { TrendingDown, AlertTriangle } from 'lucide-react';
import useCurrencyStore from '../../stores/currencyStore';

function CustomTooltip({ active, payload }) {
  const { format } = useCurrencyStore();
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload ?? {};
  return (
    <div className="glass-card-elevated px-3 py-2.5 shadow-lg min-w-[160px]">
      <p className="text-[10px] text-text-secondary mb-1.5">{d.date}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-3">
          <span className="text-xs text-negative">Drawdown</span>
          <span className="text-xs font-tabular font-semibold text-negative">-{Math.abs(d.drawdown_pct ?? 0).toFixed(2)}%</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-xs text-text-secondary">Equity</span>
          <span className="text-xs font-tabular">{format(d.equity_usd ?? 0, 2)}</span>
        </div>
      </div>
    </div>
  );
}

export default function DrawdownChart({ equityCurve, loading = false }) {
  const data = useMemo(() => {
    if (!equityCurve?.length) return [];
    return equityCurve
      .filter(p => p.date && p.date !== 'start')
      .map(p => ({
        date:         p.date,
        drawdown_pct: -(p.drawdown_pct ?? 0),
        equity_usd:   p.equity,
      }));
  }, [equityCurve]);

  const maxDd = useMemo(() => {
    if (!data.length) return 0;
    return Math.abs(Math.min(...data.map(d => d.drawdown_pct)));
  }, [data]);

  const levels = [-5, -10, -15, -20].filter(l => l > -(maxDd + 5));

  return (
    <div className="glass-card p-5">
      <div className="flex items-center gap-3 mb-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-negative-subtle">
          <TrendingDown className="h-4 w-4 text-negative" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Drawdown Analysis</h3>
          <p className="text-xs text-text-secondary">Peak-to-trough equity decline</p>
        </div>
        {maxDd > 0 && (
          <div className="ml-auto flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-negative-subtle">
            <AlertTriangle size={12} className="text-negative" />
            <span className="text-xs font-semibold text-negative">Max -{maxDd.toFixed(2)}%</span>
          </div>
        )}
      </div>

      <div className="h-[260px] w-full">
        {loading || !data.length ? (
          <div className="flex items-center justify-center h-full text-text-muted text-sm">
            {loading ? 'Running backtest…' : 'No data yet'}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="var(--color-negative)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--color-negative)" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="date"
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
                tickFormatter={(v) => `${v.toFixed(0)}%`}
                domain={[Math.min(-maxDd - 2, -1), 0.5]}
                width={45}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="var(--color-border)" strokeWidth={1} />
              {levels.map(l => (
                <ReferenceLine
                  key={l}
                  y={l}
                  stroke="var(--color-negative)"
                  strokeOpacity={0.25}
                  strokeDasharray="4 4"
                  label={{ value: `${l}%`, position: 'right', fontSize: 9, fill: 'var(--color-negative)' }}
                />
              ))}
              <Area
                type="monotone"
                dataKey="drawdown_pct"
                stroke="var(--color-negative)"
                strokeWidth={1.5}
                fill="url(#ddGradient)"
                dot={false}
                activeDot={{ r: 3, fill: 'var(--color-negative)', stroke: 'var(--color-bg)', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
