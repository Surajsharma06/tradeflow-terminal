import { useState, useMemo } from 'react';
import { Calendar, Clock } from 'lucide-react';
import { format, addDays, isToday, isTomorrow, isBefore, startOfDay } from 'date-fns';

const IMPACT_CONFIG = {
  high: { bg: 'bg-negative-subtle', text: 'text-negative', border: 'border-negative/20', label: 'High', dot: 'bg-negative' },
  medium: { bg: 'bg-warning-subtle', text: 'text-warning', border: 'border-warning/20', label: 'Medium', dot: 'bg-warning' },
  low: { bg: 'bg-positive-subtle', text: 'text-positive', border: 'border-positive/20', label: 'Low', dot: 'bg-positive' },
};

function generateEconomicEvents() {
  const now = new Date();
  const events = [];

  const templates = [
    // Indian events
    { name: 'RBI MPC Meeting', country: '🇮🇳', region: 'IN', impact: 'high', time: '10:00', category: 'Central Bank' },
    { name: 'India GDP (Q4)', country: '🇮🇳', region: 'IN', impact: 'high', time: '17:30', category: 'GDP' },
    { name: 'India CPI (YoY)', country: '🇮🇳', region: 'IN', impact: 'high', time: '17:30', category: 'Inflation' },
    { name: 'India WPI (YoY)', country: '🇮🇳', region: 'IN', impact: 'medium', time: '12:00', category: 'Inflation' },
    { name: 'Auto Sales Data', country: '🇮🇳', region: 'IN', impact: 'medium', time: '11:00', category: 'Industry' },
    { name: 'India Manufacturing PMI', country: '🇮🇳', region: 'IN', impact: 'medium', time: '10:30', category: 'PMI' },
    { name: 'India Services PMI', country: '🇮🇳', region: 'IN', impact: 'medium', time: '10:30', category: 'PMI' },
    { name: 'India Trade Balance', country: '🇮🇳', region: 'IN', impact: 'medium', time: '15:00', category: 'Trade' },
    { name: 'Union Budget 2026', country: '🇮🇳', region: 'IN', impact: 'high', time: '11:00', category: 'Fiscal' },
    { name: 'India IIP Data', country: '🇮🇳', region: 'IN', impact: 'low', time: '17:30', category: 'Industry' },

    // US events
    { name: 'US Fed Interest Rate Decision', country: '🇺🇸', region: 'US', impact: 'high', time: '00:00', category: 'Central Bank' },
    { name: 'US Non-Farm Payrolls', country: '🇺🇸', region: 'US', impact: 'high', time: '18:00', category: 'Employment' },
    { name: 'US CPI (MoM)', country: '🇺🇸', region: 'US', impact: 'high', time: '18:00', category: 'Inflation' },
    { name: 'US Core CPI (MoM)', country: '🇺🇸', region: 'US', impact: 'high', time: '18:00', category: 'Inflation' },
    { name: 'US GDP (QoQ)', country: '🇺🇸', region: 'US', impact: 'high', time: '18:00', category: 'GDP' },
    { name: 'FOMC Minutes', country: '🇺🇸', region: 'US', impact: 'high', time: '23:30', category: 'Central Bank' },
    { name: 'US Retail Sales (MoM)', country: '🇺🇸', region: 'US', impact: 'medium', time: '18:00', category: 'Consumer' },
    { name: 'US Initial Jobless Claims', country: '🇺🇸', region: 'US', impact: 'medium', time: '18:00', category: 'Employment' },
    { name: 'US ISM Manufacturing PMI', country: '🇺🇸', region: 'US', impact: 'medium', time: '19:30', category: 'PMI' },
    { name: 'US Consumer Confidence', country: '🇺🇸', region: 'US', impact: 'medium', time: '19:30', category: 'Consumer' },

    // European events
    { name: 'ECB Interest Rate Decision', country: '🇪🇺', region: 'EU', impact: 'high', time: '17:15', category: 'Central Bank' },
    { name: 'BOE Interest Rate Decision', country: '🇬🇧', region: 'UK', impact: 'high', time: '16:30', category: 'Central Bank' },
    { name: 'Eurozone CPI (YoY)', country: '🇪🇺', region: 'EU', impact: 'medium', time: '14:30', category: 'Inflation' },
    { name: 'UK GDP (QoQ)', country: '🇬🇧', region: 'UK', impact: 'medium', time: '12:30', category: 'GDP' },

    // Other
    { name: 'China GDP (YoY)', country: '🇨🇳', region: 'CN', impact: 'high', time: '07:00', category: 'GDP' },
    { name: 'BOJ Interest Rate Decision', country: '🇯🇵', region: 'JP', impact: 'high', time: '06:30', category: 'Central Bank' },
    { name: 'OPEC Monthly Report', country: '🌍', region: 'Global', impact: 'medium', time: '16:00', category: 'Energy' },
    { name: 'China Manufacturing PMI', country: '🇨🇳', region: 'CN', impact: 'medium', time: '07:00', category: 'PMI' },
  ];

  // Distribute events across next 30 days
  const shuffled = [...templates].sort(() => Math.random() - 0.5);
  shuffled.forEach((template, i) => {
    const daysAhead = Math.floor(i * 30 / shuffled.length) + Math.floor(Math.random() * 3);
    const eventDate = addDays(now, daysAhead);
    // Skip weekends
    const dow = eventDate.getDay();
    if (dow === 0 || dow === 6) return;

    events.push({
      ...template,
      id: i,
      date: eventDate,
      dateStr: format(eventDate, 'yyyy-MM-dd'),
      dateLabel: format(eventDate, 'EEE, dd MMM'),
      isPast: isBefore(eventDate, startOfDay(now)),
    });
  });

  return events.sort((a, b) => a.date - b.date);
}

export default function EconomicCalendar({ className = '' }) {
  const [filter, setFilter] = useState('all');
  const [impactFilter, setImpactFilter] = useState('all');

  const allEvents = useMemo(() => generateEconomicEvents(), []);

  const filteredEvents = useMemo(() => {
    return allEvents.filter((e) => {
      if (filter !== 'all' && e.region !== filter) return false;
      if (impactFilter !== 'all' && e.impact !== impactFilter) return false;
      return true;
    });
  }, [allEvents, filter, impactFilter]);

  // Group by date
  const grouped = useMemo(() => {
    const groups = {};
    filteredEvents.forEach((e) => {
      if (!groups[e.dateStr]) {
        groups[e.dateStr] = { date: e.date, dateLabel: e.dateLabel, events: [] };
      }
      groups[e.dateStr].events.push(e);
    });
    return Object.values(groups);
  }, [filteredEvents]);

  const highImpactCount = allEvents.filter(e => e.impact === 'high' && !e.isPast).length;

  return (
    <div className={`glass-card p-5 ${className}`}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-info-subtle">
            <Calendar className="h-4.5 w-4.5 text-info" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Economic Calendar</h3>
            <p className="text-xs text-text-secondary">
              Upcoming market-moving events • {highImpactCount} high impact
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <div className="flex gap-1 rounded-lg bg-surface p-0.5">
            {[
              { key: 'all', label: '🌍 All' },
              { key: 'IN', label: '🇮🇳' },
              { key: 'US', label: '🇺🇸' },
              { key: 'EU', label: '🇪🇺' },
              { key: 'UK', label: '🇬🇧' },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-2.5 py-1 text-xs rounded-md transition-all duration-200
                  ${filter === key
                    ? 'bg-accent text-white'
                    : 'text-text-secondary hover:bg-surface-hover'
                  }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex gap-1 rounded-lg bg-surface p-0.5">
            {['all', 'high', 'medium', 'low'].map((level) => (
              <button
                key={level}
                onClick={() => setImpactFilter(level)}
                className={`px-2 py-1 text-xs rounded-md transition-all duration-200 capitalize
                  ${impactFilter === level
                    ? 'bg-accent text-white'
                    : 'text-text-secondary hover:bg-surface-hover'
                  }`}
              >
                {level === 'all' ? 'All' : level.charAt(0).toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Events list */}
      <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
        {grouped.map((group) => {
          const isCurrentDay = isToday(group.date);
          const isTomorrowDay = isTomorrow(group.date);

          return (
            <div key={group.dateLabel}>
              {/* Date header */}
              <div className="flex items-center gap-2 mb-2 sticky top-0 bg-surface/80 backdrop-blur-sm py-1.5 px-2 rounded-md -mx-1">
                <span className={`text-xs font-semibold ${isCurrentDay ? 'text-accent' : 'text-text-secondary'}`}>
                  {isCurrentDay ? '📌 Today' : isTomorrowDay ? '📅 Tomorrow' : group.dateLabel}
                </span>
                {isCurrentDay && (
                  <span className="status-dot status-dot-live" />
                )}
                <span className="text-[10px] text-text-tertiary">
                  ({group.events.length} events)
                </span>
              </div>

              {/* Events */}
              <div className="space-y-1.5">
                {group.events.map((event) => {
                  const impact = IMPACT_CONFIG[event.impact];
                  return (
                    <div
                      key={event.id}
                      className={`
                        flex items-center gap-3 px-3 py-2.5 rounded-lg
                        transition-all duration-200 hover:bg-surface-hover border border-transparent
                        ${event.isPast ? 'opacity-40' : ''}
                        ${event.impact === 'high' && !event.isPast ? 'hover:border-negative/20' : ''}
                      `}
                    >
                      {/* Time */}
                      <div className="flex items-center gap-1.5 min-w-[65px]">
                        <Clock className="h-3 w-3 text-text-tertiary" />
                        <span className="text-xs font-mono font-tabular text-text-secondary">
                          {event.time} IST
                        </span>
                      </div>

                      {/* Country flag */}
                      <span className="text-base">{event.country}</span>

                      {/* Event name */}
                      <div className="flex-1 min-w-0">
                        <span className={`text-sm font-medium ${event.impact === 'high' ? 'text-text-primary' : 'text-text-secondary'}`}>
                          {event.name}
                        </span>
                      </div>

                      {/* Category tag */}
                      <span className="hidden sm:inline text-[10px] px-2 py-0.5 rounded-md bg-surface text-text-tertiary font-medium">
                        {event.category}
                      </span>

                      {/* Impact badge */}
                      <span className={`
                        inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold border
                        ${impact.bg} ${impact.text} ${impact.border}
                      `}>
                        <span className={`h-1.5 w-1.5 rounded-full ${impact.dot}`} />
                        {impact.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        {grouped.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-text-tertiary">
            <Calendar className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-sm">No events match your filters</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
        <span className="text-[10px] text-text-tertiary">
          All times in IST (UTC+5:30) • Data for next 30 days
        </span>
        <div className="flex items-center gap-3">
          {Object.entries(IMPACT_CONFIG).map(([key, config]) => (
            <div key={key} className="flex items-center gap-1">
              <span className={`h-2 w-2 rounded-full ${config.dot}`} />
              <span className="text-[10px] text-text-tertiary">{config.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
