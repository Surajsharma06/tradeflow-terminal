import { useEffect, useState } from 'react';
import {
  Wrench,
  Calculator,
  Receipt,
  CalendarDays,
} from 'lucide-react';

import PositionCalculator from '../components/tools/PositionCalculator';
import ChargesCalculator from '../components/tools/ChargesCalculator';
import EconomicCalendar from '../components/tools/EconomicCalendar';

// ═══════════════════════════════════════════════════════
// Tools Page — Trading Utilities & Calculators
// ═══════════════════════════════════════════════════════

const TOOL_SECTIONS = [
  {
    id: 'position',
    title: 'Position Size Calculator',
    subtitle: 'Calculate optimal position size based on risk parameters',
    icon: Calculator,
    iconColor: 'text-accent',
    Component: PositionCalculator,
  },
  {
    id: 'charges',
    title: 'Brokerage & Charges Calculator',
    subtitle: 'Estimate STT, brokerage, stamp duty, GST for any trade',
    icon: Receipt,
    iconColor: 'text-gold',
    Component: ChargesCalculator,
  },
  {
    id: 'calendar',
    title: 'Economic Calendar',
    subtitle: 'Upcoming macro events, RBI policy, earnings & market holidays',
    icon: CalendarDays,
    iconColor: 'text-purple',
    Component: EconomicCalendar,
  },
];

export default function ToolsPage() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  const stagger = (index) => ({
    opacity: mounted ? 1 : 0,
    transform: mounted ? 'translateY(0px)' : 'translateY(20px)',
    transition: `all 0.5s cubic-bezier(0.16, 1, 0.3, 1) ${index * 0.1}s`,
  });

  return (
    <div className="p-4 lg:p-6 min-h-screen">
      {/* ── Header ── */}
      <div style={stagger(0)} className="mb-6">
        <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
          <Wrench className="w-6 h-6 text-accent" />
          Trading Tools
        </h1>
        <p className="text-xs text-text-tertiary mt-0.5">
          Position sizing, charges estimation, and market event tracking
        </p>
      </div>

      {/* ── Quick Navigation Pills ── */}
      <div style={stagger(1)} className="mb-6 flex items-center gap-2 flex-wrap">
        {TOOL_SECTIONS.map((section) => (
          <a
            key={section.id}
            href={`#tool-${section.id}`}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-border text-xs font-medium text-text-secondary hover:text-text-primary hover:border-border-light hover:bg-surface-hover transition-all"
          >
            <section.icon className={`w-3.5 h-3.5 ${section.iconColor}`} />
            {section.title}
          </a>
        ))}
      </div>

      {/* ── Tool Sections ── */}
      <div className="space-y-6">
        {TOOL_SECTIONS.map((section, index) => (
          <div
            key={section.id}
            id={`tool-${section.id}`}
            style={stagger(index + 2)}
            className="scroll-mt-20"
          >
            {/* Section Header */}
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-surface-elevated border border-border/50 flex items-center justify-center">
                <section.icon className={`w-4 h-4 ${section.iconColor}`} />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-text-primary">
                  {section.title}
                </h2>
                <p className="text-[10px] text-text-muted">{section.subtitle}</p>
              </div>
            </div>

            {/* Component */}
            <section.Component />
          </div>
        ))}
      </div>
    </div>
  );
}
