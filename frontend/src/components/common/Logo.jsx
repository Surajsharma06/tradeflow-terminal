/**
 * TradeFlow 3.0 brand mark.
 *
 * Abstract "flow" mark: two rising streams converging into an arrow tip —
 * evokes market momentum and the Flow in TradeFlow without candlestick
 * clichés. Gradient accent→purple, themeable, crisp at 16px.
 */

export function LogoMark({ size = 32, rounded = true, className = '' }) {
  const id = 'tfFlowGrad';
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="TradeFlow logo"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#388bfd" />
          <stop offset="100%" stopColor="#bc8cff" />
        </linearGradient>
      </defs>
      {rounded && <rect width="32" height="32" rx="8" fill="#0d1117" />}
      <path
        d="M5 21.5 C10 21.5 12 14.5 16.5 14.5 C21 14.5 22.5 9.5 27 9"
        stroke={`url(#${id})`}
        strokeWidth="2.6"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M5 26 C11 26 13.5 20.5 18 20.5 C22.5 20.5 24.5 17 27 16.2"
        stroke={`url(#${id})`}
        strokeWidth="2.6"
        fill="none"
        strokeLinecap="round"
        opacity="0.45"
      />
      <path
        d="M22.2 6.4 L27 9 L24.6 13.9"
        stroke="#bc8cff"
        strokeWidth="2.6"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function LogoWordmark({ collapsed = false }) {
  return (
    <div className="flex items-center gap-3">
      <LogoMark size={36} />
      {!collapsed && (
        <div className="flex flex-col overflow-hidden">
          <span className="text-sm font-bold text-text-primary tracking-tight leading-tight">
            TradeFlow
          </span>
          <span className="text-[9px] font-semibold text-accent uppercase tracking-widest">
            Terminal v3.0
          </span>
        </div>
      )}
    </div>
  );
}

export default LogoMark;
