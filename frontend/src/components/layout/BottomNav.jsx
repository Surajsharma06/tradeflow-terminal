import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Globe, Bitcoin, BarChart3, Menu } from 'lucide-react';

// ══════════════════════════════════════════════════════════════════
//  MOBILE BOTTOM NAVIGATION
//  App-style tab bar (mobile only) with a raised centre action button.
//  Hidden on md+ where the sidebar takes over.
// ══════════════════════════════════════════════════════════════════

const ITEMS = [
  { to: '/',          icon: LayoutDashboard, label: 'Home' },
  { to: '/forex',     icon: Globe,           label: 'Forex' },
  { to: '/crypto',    icon: Bitcoin,         label: 'Crypto', center: true },
  { to: '/analytics', icon: BarChart3,       label: 'Stats' },
];

export default function BottomNav() {
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-bg-alt/92 backdrop-blur-xl border-t border-border/60"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      aria-label="Primary"
    >
      <div className="flex items-end justify-around h-16 px-2">
        {ITEMS.map(({ to, icon: Icon, label, center }) =>
          center ? (
            // Raised centre action — the floating lime button from the reference
            <NavLink key={to} to={to} className="relative flex flex-col items-center justify-end -mt-6 flex-1">
              {({ isActive }) => (
                <>
                  <span
                    className={`flex items-center justify-center w-14 h-14 rounded-full btn-gradient text-on-accent shadow-lg transition-transform active:scale-95 ${
                      isActive ? 'ring-2 ring-accent/40' : ''
                    }`}
                  >
                    <Icon size={24} />
                  </span>
                  <span className="text-[9px] font-semibold mt-1 text-text-tertiary">{label}</span>
                </>
              )}
            </NavLink>
          ) : (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className="flex flex-col items-center justify-center gap-1 flex-1 h-full min-w-[44px]"
            >
              {({ isActive }) => (
                <>
                  <Icon size={21} className={isActive ? 'text-accent' : 'text-text-tertiary'} />
                  <span className={`text-[9px] font-semibold ${isActive ? 'text-accent' : 'text-text-tertiary'}`}>
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          )
        )}

        {/* More — opens the mobile drawer (Commodity, Tools, Settings, theme…) */}
        <button
          onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
          className="flex flex-col items-center justify-center gap-1 flex-1 h-full min-w-[44px] text-text-tertiary active:text-accent"
          aria-label="More menu"
        >
          <Menu size={21} />
          <span className="text-[9px] font-semibold">More</span>
        </button>
      </div>
    </nav>
  );
}
