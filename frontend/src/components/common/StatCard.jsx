import { useEffect, useRef, useState } from 'react';
import { TrendingUp, TrendingDown, Minus, ArrowUpRight, ArrowDownRight } from 'lucide-react';

const TREND_CONFIG = {
  up: {
    icon: TrendingUp,
    arrowIcon: ArrowUpRight,
    color: 'text-positive',
    bgColor: 'bg-positive-subtle',
    badgeBg: 'bg-positive-subtle',
    badgeText: 'text-positive',
  },
  down: {
    icon: TrendingDown,
    arrowIcon: ArrowDownRight,
    color: 'text-negative',
    bgColor: 'bg-negative-subtle',
    badgeBg: 'bg-negative-subtle',
    badgeText: 'text-negative',
  },
  flat: {
    icon: Minus,
    arrowIcon: Minus,
    color: 'text-text-secondary',
    bgColor: 'bg-surface-hover',
    badgeBg: 'bg-surface-hover',
    badgeText: 'text-text-secondary',
  },
};

function useCountUp(end, duration = 1200, decimals = 2) {
  const [value, setValue] = useState(0);
  const frameRef = useRef(null);
  const startTimeRef = useRef(null);

  useEffect(() => {
    const numericEnd = typeof end === 'number' ? end : parseFloat(String(end).replace(/[^0-9.-]/g, ''));
    if (isNaN(numericEnd)) {
      setValue(end);
      return;
    }

    startTimeRef.current = performance.now();

    const animate = (now) => {
      const elapsed = now - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = numericEnd * eased;

      setValue(Number(current.toFixed(decimals)));

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [end, duration, decimals]);

  return value;
}

export default function StatCard({
  title,
  value,
  prefix = '',
  suffix = '',
  change,
  changePercent,
  icon: Icon,
  trend = 'flat',
  decimals = 2,
  className = '',
}) {
  const config = TREND_CONFIG[trend] || TREND_CONFIG.flat;
  const ArrowIcon = config.arrowIcon;

  const numericValue = typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ''));
  const animatedValue = useCountUp(isNaN(numericValue) ? 0 : numericValue, 1200, decimals);

  const displayValue = isNaN(numericValue)
    ? value
    : `${prefix}${animatedValue.toLocaleString('en-IN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}${suffix}`;

  return (
    <div
      className={`glass-card hover-lift group relative overflow-hidden p-4 transition-all duration-300 ${className}`}
    >
      {/* Subtle gradient overlay on hover */}
      <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

      <div className="relative z-10 flex items-start justify-between">
        {/* Left side: title + value */}
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-text-secondary mb-1.5">
            {title}
          </p>
          <p className="text-2xl font-semibold font-mono font-tabular text-text-primary leading-tight truncate">
            {displayValue}
          </p>

          {/* Change badge */}
          {(change !== undefined || changePercent !== undefined) && (
            <div className="mt-2 flex items-center gap-1.5">
              <span
                className={`inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-xs font-medium ${config.badgeBg} ${config.badgeText}`}
              >
                <ArrowIcon className="h-3 w-3" />
                {changePercent !== undefined && (
                  <span className="font-mono font-tabular">
                    {changePercent > 0 ? '+' : ''}{changePercent}%
                  </span>
                )}
              </span>
              {change !== undefined && (
                <span className={`text-xs font-mono font-tabular ${config.color}`}>
                  {change > 0 ? '+' : ''}{typeof change === 'number' ? change.toLocaleString('en-IN') : change}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Right side: icon */}
        {Icon && (
          <div
            className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${config.bgColor} transition-transform duration-300 group-hover:scale-110`}
          >
            <Icon className={`h-5 w-5 ${config.color}`} />
          </div>
        )}
      </div>
    </div>
  );
}
