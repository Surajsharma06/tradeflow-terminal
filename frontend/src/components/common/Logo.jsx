/**
 * TradeShield brand mark.
 *
 * Custom logo: shield + handshake + rising arrow — trust, partnership and
 * upward momentum. Rendered from the raster asset in /public so it stays
 * crisp on retina at the small sizes used across the app.
 */

export function LogoMark({ size = 32, rounded = true, className = '' }) {
  return (
    <img
      src="/brand-logo.png"
      width={size}
      height={size}
      alt="TradeShield logo"
      className={`object-contain bg-white ${rounded ? 'rounded-[26%]' : ''} ${className}`}
      style={{ width: size, height: size, boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.04)' }}
      draggable={false}
    />
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
