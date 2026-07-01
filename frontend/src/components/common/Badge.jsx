const VARIANT_STYLES = {
  success: {
    bg: 'bg-positive-subtle',
    text: 'text-positive',
    dot: 'bg-positive',
    border: 'border-positive/20',
  },
  danger: {
    bg: 'bg-negative-subtle',
    text: 'text-negative',
    dot: 'bg-negative',
    border: 'border-negative/20',
  },
  warning: {
    bg: 'bg-warning-subtle',
    text: 'text-warning',
    dot: 'bg-warning',
    border: 'border-warning/20',
  },
  info: {
    bg: 'bg-info-subtle',
    text: 'text-info',
    dot: 'bg-info',
    border: 'border-info/20',
  },
  neutral: {
    bg: 'bg-surface-hover',
    text: 'text-text-secondary',
    dot: 'bg-text-secondary',
    border: 'border-border',
  },
  bull: {
    bg: 'bg-positive-subtle',
    text: 'text-positive',
    dot: 'bg-positive',
    border: 'border-positive/20',
  },
  bear: {
    bg: 'bg-negative-subtle',
    text: 'text-negative',
    dot: 'bg-negative',
    border: 'border-negative/20',
  },
  sideways: {
    bg: 'bg-warning-subtle',
    text: 'text-warning',
    dot: 'bg-warning',
    border: 'border-warning/20',
  },
};

const SIZE_STYLES = {
  xs: 'px-1.5 py-0.5 text-[10px]',
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
};

export default function Badge({
  text,
  variant = 'neutral',
  size = 'sm',
  dot = false,
  pulse = false,
  icon: Icon,
  className = '',
}) {
  const styles = VARIANT_STYLES[variant] || VARIANT_STYLES.neutral;
  const sizeClass = SIZE_STYLES[size] || SIZE_STYLES.sm;

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-md font-medium border
        transition-all duration-200
        ${styles.bg} ${styles.text} ${styles.border}
        ${sizeClass}
        ${className}
      `}
    >
      {dot && (
        <span className="relative flex h-2 w-2">
          {pulse && (
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${styles.dot}`}
            />
          )}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${styles.dot}`} />
        </span>
      )}
      {Icon && <Icon className="h-3 w-3" />}
      {text}
    </span>
  );
}
