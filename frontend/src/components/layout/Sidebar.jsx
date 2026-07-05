import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  BarChart3,
  FlaskConical,
  Wrench,
  Settings,
  ChevronLeft,
  ChevronRight,
  X,
  Wifi,
  WifiOff,
  Globe,
  ShieldCheck,
} from 'lucide-react';
import { LogoMark } from '../common/Logo';

const NAV_ITEMS = [
  { to: '/',           icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/forex',      icon: Globe,           label: 'Forex' },
  { to: '/discipline', icon: ShieldCheck,     label: 'Legends', badge: 'NEW' },
  { to: '/analytics',  icon: BarChart3,        label: 'Analytics' },
  { to: '/backtest',   icon: FlaskConical,     label: 'Backtest'  },
  { to: '/tools',      icon: Wrench,           label: 'Tools'     },
  { to: '/settings',   icon: Settings,         label: 'Settings'  },
];

function PaperTradingToggle({ collapsed }) {
  const [enabled, setEnabled] = useState(true);
  return (
    <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2.5 px-3'}`}>
      <button
        onClick={() => setEnabled(!enabled)}
        className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-300 ease-in-out focus:outline-none ${
          enabled ? 'bg-accent' : 'bg-surface-active'
        }`}
        role="switch"
        aria-checked={enabled}
        title={collapsed ? (enabled ? 'Paper Trading ON' : 'Paper Trading OFF') : ''}
      >
        <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition-transform duration-300 ease-in-out ${
          enabled ? 'translate-x-4' : 'translate-x-0'
        }`} />
      </button>
      {!collapsed && (
        <div className="flex flex-col">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">Paper Trading</span>
          <span className={`text-[9px] font-bold uppercase tracking-wider ${enabled ? 'text-accent' : 'text-text-muted'}`}>
            {enabled ? 'ACTIVE' : 'OFF'}
          </span>
        </div>
      )}
    </div>
  );
}

function ConnectionStatus({ collapsed, connected = true }) {
  return (
    <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2 px-3'}`}>
      <div className={`flex items-center justify-center w-6 h-6 rounded-md ${connected ? 'bg-positive-subtle' : 'bg-negative-subtle'}`}>
        {connected ? <Wifi size={12} className="text-positive" /> : <WifiOff size={12} className="text-negative" />}
      </div>
      {!collapsed && (
        <div className="flex flex-col">
          <span className="text-[10px] text-text-tertiary">Server</span>
          <span className={`text-[9px] font-bold uppercase ${connected ? 'text-positive' : 'text-negative'}`}>
            {connected ? 'CONNECTED' : 'OFFLINE'}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Inner sidebar contents ────────────────────────────────────────
function SidebarContents({ collapsed, onClose }) {
  return (
    <>
      {/* Logo area */}
      <div className={`flex items-center h-14 border-b border-border/30 ${collapsed ? 'justify-center px-2' : 'px-4 gap-3'}`}>
        <div className="flex-shrink-0 shadow-lg shadow-accent/20 rounded-lg">
          <LogoMark size={36} />
        </div>
        {!collapsed && (
          <div className="flex flex-col overflow-hidden flex-1">
            <span className="text-sm font-bold text-text-primary tracking-tight leading-tight">TradeFlow</span>
            <span className="text-[9px] font-semibold text-accent uppercase tracking-widest">Terminal v3.0</span>
          </div>
        )}
        {/* Mobile close button — 44x44 tap target */}
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden flex items-center justify-center min-w-[44px] min-h-[44px] -mr-2 rounded-md hover:bg-surface-hover text-text-secondary cursor-pointer"
            aria-label="Close navigation menu"
          >
            <X size={20} />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              `group relative flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-3'} py-2.5 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'nav-active text-accent'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full bg-accent shadow-[0_0_8px_rgba(56,139,253,0.6)]" />
                )}
                <item.icon size={19} className={`flex-shrink-0 transition-colors duration-200 ${
                  isActive ? 'text-accent' : 'text-text-tertiary group-hover:text-text-primary'
                }`} />
                {!collapsed && (
                  <span className={`flex-1 text-sm font-medium transition-colors duration-200 ${isActive ? 'text-accent' : ''}`}>
                    {item.label}
                  </span>
                )}
                {!collapsed && item.badge && (
                  <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-full badge-gradient text-white tracking-wider">
                    {item.badge}
                  </span>
                )}
                {collapsed && (
                  <div className="absolute left-full ml-2 px-2.5 py-1 rounded-md bg-surface-elevated border border-border text-xs font-medium text-text-primary opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-50 shadow-elevated">
                    {item.label}
                  </div>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-border/30 py-3 space-y-3">
        <PaperTradingToggle collapsed={collapsed} />
        <ConnectionStatus collapsed={collapsed} />
        {/* Collapse toggle (desktop only) */}
        <div className={`hidden md:flex ${collapsed ? 'justify-center' : 'px-3'}`}>
          <button
            onClick={onClose}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-surface-hover hover:bg-surface-active text-text-secondary hover:text-text-primary transition-all duration-200"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
//  SIDEBAR COMPONENT
// ══════════════════════════════════════════════════════════════════
export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handler = () => setMobileOpen(o => !o);
    window.addEventListener('sidebar-toggle', handler);
    return () => window.removeEventListener('sidebar-toggle', handler);
  }, []);

  // Lock body scroll while the mobile drawer is open, close on Escape.
  useEffect(() => {
    if (!mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e) => { if (e.key === 'Escape') setMobileOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener('keydown', onKey);
    };
  }, [mobileOpen]);

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 z-40 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Desktop sidebar */}
      <aside
        className={`hidden md:flex flex-col h-full bg-bg-alt/60 backdrop-blur-xl border-r border-border/50 transition-all duration-300 ease-in-out select-none ${
          collapsed ? 'w-[68px]' : 'w-[220px]'
        }`}
      >
        <SidebarContents collapsed={collapsed} onClose={() => setCollapsed(c => !c)} />
      </aside>

      {/* Mobile sidebar (overlay) */}
      <aside
        className={`md:hidden fixed inset-y-0 left-0 z-50 flex flex-col w-[240px] bg-bg-alt backdrop-blur-xl border-r border-border/50 transition-transform duration-300 ease-in-out select-none ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <SidebarContents collapsed={false} onClose={() => setMobileOpen(false)} />
      </aside>
    </>
  );
}
