import { useState, useEffect, useRef } from 'react';
import {
  Shield,
  TrendingDown,
  Layers,
  IndianRupee,
} from 'lucide-react';

// ── Mock risk data ────────────────────────────────────────────────
const RISK_DATA = {
  capitalAtRisk: 24.5,       // percentage
  absoluteAmount: 245000,    // ₹
  totalCapital: 1000000,     // ₹
  openPositions: 4,
  dailyPnl: 18750,           // ₹
  dailyPnlPct: 1.87,         // %
  maxDrawdown: 5.2,          // %
  drawdownAmount: 52000,     // ₹
};

// ── Animated circular gauge ───────────────────────────────────────
function CircularGauge({ percentage, animated = true }) {
  const [animatedPct, setAnimatedPct] = useState(0);
  const animRef = useRef(null);

  useEffect(() => {
    if (!animated) {
      setAnimatedPct(percentage);
      return;
    }

    const start = performance.now();
    const duration = 1400;

    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedPct(eased * percentage);

      if (progress < 1) {
        animRef.current = requestAnimationFrame(animate);
      }
    };

    animRef.current = requestAnimationFrame(animate);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [percentage, animated]);

  const size = 180;
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const arc = circumference * 0.75; // 270 degrees
  const offset = arc - (arc * animatedPct) / 100;

  // Color based on risk level
  const getColor = (pct) => {
    if (pct < 30) return { stroke: 'var(--color-positive)', glow: 'rgba(63,185,80,0.3)', label: 'LOW', labelColor: 'text-positive' };
    if (pct < 60) return { stroke: 'var(--color-warning)', glow: 'rgba(210,153,34,0.3)', label: 'MODERATE', labelColor: 'text-warning' };
    return { stroke: 'var(--color-negative)', glow: 'rgba(248,81,73,0.3)', label: 'HIGH', labelColor: 'text-negative' };
  };

  const color = getColor(animatedPct);

  return (
    <div className="relative flex items-center justify-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="transform -rotate-[135deg]"
      >
        {/* Background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-surface-active)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${arc} ${circumference}`}
          opacity={0.4}
        />

        {/* Colored segments (background hints) */}
        {/* Green zone 0-30% */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-positive)"
          strokeWidth={2}
          strokeDasharray={`${arc * 0.3} ${circumference}`}
          opacity={0.15}
        />
        {/* Amber zone 30-60% */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-warning)"
          strokeWidth={2}
          strokeDasharray={`${arc * 0.3} ${circumference}`}
          strokeDashoffset={-arc * 0.3}
          opacity={0.15}
        />
        {/* Red zone 60-100% */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-negative)"
          strokeWidth={2}
          strokeDasharray={`${arc * 0.4} ${circumference}`}
          strokeDashoffset={-arc * 0.6}
          opacity={0.15}
        />

        {/* Active progress arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color.stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${arc} ${circumference}`}
          strokeDashoffset={offset}
          style={{
            filter: `drop-shadow(0 0 6px ${color.glow})`,
            transition: 'stroke 0.3s ease',
          }}
        />

        {/* Dot at the end of progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="transparent"
          strokeWidth={0}
        />
      </svg>

      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center transform rotate-0">
        <span className="text-[10px] font-semibold text-text-tertiary uppercase tracking-widest mb-1">
          Capital at Risk
        </span>
        <span className="font-tabular text-3xl font-bold text-text-primary leading-none">
          {animatedPct.toFixed(1)}%
        </span>
        <span className="font-tabular text-xs text-text-secondary mt-1">
          ₹{(RISK_DATA.absoluteAmount / 1000).toFixed(0)}K / ₹{(RISK_DATA.totalCapital / 100000).toFixed(0)}L
        </span>
        <span className={`text-[9px] font-bold uppercase tracking-wider mt-1.5 ${color.labelColor}`}>
          {color.label} RISK
        </span>
      </div>
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────
function StatItem({ icon: Icon, iconColor, label, value, subValue, valueColor }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-surface/40 hover:bg-surface-hover/40 transition-colors duration-200">
      <div className={`flex items-center justify-center w-8 h-8 rounded-lg ${iconColor}`}>
        <Icon size={15} />
      </div>
      <div className="flex flex-col flex-1 min-w-0">
        <span className="text-[10px] text-text-tertiary uppercase tracking-wider font-medium">
          {label}
        </span>
        <span className={`font-tabular text-sm font-bold ${valueColor || 'text-text-primary'}`}>
          {value}
        </span>
      </div>
      {subValue && (
        <span className={`font-tabular text-[10px] font-semibold ${valueColor || 'text-text-secondary'}`}>
          {subValue}
        </span>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
//  RISK METER COMPONENT
// ══════════════════════════════════════════════════════════════════
export default function RiskMeter() {
  const dailyPositive = RISK_DATA.dailyPnl >= 0;

  return (
    <section className="glass-card p-4 animate-slide-up">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Shield size={16} className="text-accent" />
        <h3 className="text-sm font-semibold text-text-primary">Risk Monitor</h3>
      </div>

      {/* Gauge */}
      <div className="flex justify-center mb-4">
        <CircularGauge percentage={RISK_DATA.capitalAtRisk} />
      </div>

      {/* Stats */}
      <div className="space-y-2">
        <StatItem
          icon={Layers}
          iconColor="bg-purple-subtle text-purple"
          label="Open Positions"
          value={RISK_DATA.openPositions}
        />
        <StatItem
          icon={IndianRupee}
          iconColor={dailyPositive ? 'bg-positive-subtle text-positive' : 'bg-negative-subtle text-negative'}
          label="Daily P&L"
          value={`${dailyPositive ? '+' : '-'}₹${Math.abs(RISK_DATA.dailyPnl).toLocaleString('en-IN')}`}
          subValue={`${dailyPositive ? '+' : ''}${RISK_DATA.dailyPnlPct}%`}
          valueColor={dailyPositive ? 'text-positive' : 'text-negative'}
        />
        <StatItem
          icon={TrendingDown}
          iconColor="bg-negative-subtle text-negative"
          label="Max Drawdown"
          value={`${RISK_DATA.maxDrawdown}%`}
          subValue={`₹${(RISK_DATA.drawdownAmount / 1000).toFixed(0)}K`}
          valueColor="text-negative"
        />
      </div>
    </section>
  );
}
