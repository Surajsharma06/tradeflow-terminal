import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import {
  startOfMonth, endOfMonth, eachDayOfInterval, getDay, subMonths, addMonths, format,
} from 'date-fns';
import useCurrencyStore from '../../stores/currencyStore';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function getPnLColor(value, maxAbs) {
  if (value === undefined || value === null) return '';
  const intensity = Math.min(Math.abs(value) / Math.max(maxAbs, 1), 1);
  if (value > 0)  return `rgba(63, 185, 80, ${0.15 + intensity * 0.65})`;
  if (value < 0)  return `rgba(248, 81, 73, ${0.15 + intensity * 0.65})`;
  return 'rgba(139, 148, 158, 0.1)';
}

export default function PnLCalendar({ calendarPnl, monthlyPnl, loading = false, className = '' }) {
  const [currentDate, setCurrentDate]   = useState(new Date());
  const [hoveredDay, setHoveredDay]     = useState(null);
  const { format: fmtCurrency }         = useCurrencyStore();

  const year  = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const daysInMonth = useMemo(() => {
    const start    = startOfMonth(new Date(year, month));
    const end      = endOfMonth(start);
    const startDow = getDay(start);
    const days     = eachDayOfInterval({ start, end });
    const blanks   = Array.from({ length: startDow }).map((_, i) => ({ key: `b${i}`, blank: true }));
    return [
      ...blanks,
      ...days.map(d => ({ key: format(d, 'yyyy-MM-dd'), date: d, dateStr: format(d, 'yyyy-MM-dd') })),
    ];
  }, [year, month]);

  const maxAbs = useMemo(() => {
    if (!calendarPnl) return 1;
    return Math.max(...Object.values(calendarPnl).map(Math.abs), 1);
  }, [calendarPnl]);

  const monthKey = format(new Date(year, month), 'yyyy-MM');
  const monthTotal = useMemo(() => {
    if (monthlyPnl) {
      const entry = monthlyPnl.find(m => m.month === monthKey);
      return entry?.pnl_usd ?? null;
    }
    if (calendarPnl) {
      return Object.entries(calendarPnl)
        .filter(([k]) => k.startsWith(monthKey))
        .reduce((acc, [, v]) => acc + v, 0);
    }
    return null;
  }, [calendarPnl, monthlyPnl, monthKey]);

  return (
    <div className={`glass-card p-5 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-subtle">
            <Calendar className="h-4 w-4 text-accent" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">P&L Calendar</h3>
            <p className="text-xs text-text-secondary">
              {format(new Date(year, month), 'MMMM yyyy')}
              {monthTotal !== null && (
                <span className={`ml-2 font-semibold ${monthTotal >= 0 ? 'text-positive' : 'text-negative'}`}>
                  {monthTotal >= 0 ? '+' : ''}{fmtCurrency(monthTotal, 2)}
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setCurrentDate(subMonths(currentDate, 1))}
            className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary cursor-pointer">
            <ChevronLeft size={16} />
          </button>
          <button onClick={() => setCurrentDate(addMonths(currentDate, 1))}
            className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary cursor-pointer">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="h-48 flex items-center justify-center text-text-muted text-sm">Running backtest…</div>
      ) : (
        <div className="relative">
          <div className="grid grid-cols-7 gap-1 mb-1">
            {WEEKDAYS.map(d => (
              <div key={d} className="text-center text-[10px] font-medium text-text-tertiary py-1">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {daysInMonth.map((cell) => {
              if (cell.blank) return <div key={cell.key} />;
              const pnl   = calendarPnl?.[cell.dateStr] ?? null;
              const color = pnl !== null ? getPnLColor(pnl, maxAbs) : '';
              return (
                <div
                  key={cell.key}
                  className="relative aspect-square rounded-md flex items-center justify-center cursor-default transition-all duration-150 hover:ring-1 hover:ring-accent/40"
                  style={{ backgroundColor: color || 'rgba(139,148,158,0.05)' }}
                  onMouseEnter={() => setHoveredDay(cell.dateStr)}
                  onMouseLeave={() => setHoveredDay(null)}
                >
                  <span className={`text-[10px] font-medium ${pnl > 0 ? 'text-positive' : pnl < 0 ? 'text-negative' : 'text-text-muted'}`}>
                    {format(cell.date, 'd')}
                  </span>
                  {hoveredDay === cell.dateStr && pnl !== null && (
                    <div className="absolute z-20 bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2.5 py-1.5 rounded-lg bg-surface-elevated border border-border shadow-elevated whitespace-nowrap pointer-events-none">
                      <p className="text-[10px] text-text-secondary">{format(cell.date, 'dd MMM yyyy')}</p>
                      <p className={`text-xs font-tabular font-semibold ${pnl >= 0 ? 'text-positive' : 'text-negative'}`}>
                        {pnl >= 0 ? '+' : ''}{fmtCurrency(pnl, 2)}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex items-center justify-between mt-3 text-[10px] text-text-tertiary">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(248,81,73,0.6)' }} />
              Loss
            </div>
            {!calendarPnl && <span className="italic">No backtest data yet</span>}
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(63,185,80,0.6)' }} />
              Profit
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
