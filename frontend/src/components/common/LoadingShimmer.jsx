const PRESETS = {
  line: (w, h) => (
    <div className="space-y-2.5">
      <div className="shimmer rounded-md" style={{ width: w || '100%', height: h || '14px' }} />
      <div className="shimmer rounded-md" style={{ width: '75%', height: h || '14px' }} />
      <div className="shimmer rounded-md" style={{ width: '60%', height: h || '14px' }} />
    </div>
  ),

  card: (w, h) => (
    <div
      className="glass-card overflow-hidden"
      style={{ width: w || '100%', height: h || '180px' }}
    >
      <div className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="shimmer h-4 w-24 rounded-md" />
          <div className="shimmer h-8 w-8 rounded-lg" />
        </div>
        {/* Value */}
        <div className="shimmer h-8 w-36 rounded-md" />
        {/* Change badge */}
        <div className="flex items-center gap-2">
          <div className="shimmer h-5 w-16 rounded-md" />
          <div className="shimmer h-4 w-12 rounded-md" />
        </div>
      </div>
    </div>
  ),

  chart: (w, h) => (
    <div
      className="glass-card overflow-hidden"
      style={{ width: w || '100%', height: h || '300px' }}
    >
      <div className="p-4 space-y-3 h-full flex flex-col">
        {/* Chart header */}
        <div className="flex items-center justify-between">
          <div className="shimmer h-5 w-32 rounded-md" />
          <div className="flex gap-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="shimmer h-6 w-10 rounded-md" />
            ))}
          </div>
        </div>
        {/* Chart area */}
        <div className="flex-1 flex items-end gap-1 px-2 pb-2">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="shimmer flex-1 rounded-t-sm"
              style={{ height: `${25 + Math.random() * 60}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  ),

  table: (w, h) => (
    <div
      className="glass-card overflow-hidden"
      style={{ width: w || '100%', height: h || '320px' }}
    >
      <div className="p-4 space-y-2">
        {/* Table header */}
        <div className="flex gap-4 pb-2 border-b border-border">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="shimmer h-4 flex-1 rounded-md" />
          ))}
        </div>
        {/* Table rows */}
        {[...Array(6)].map((_, row) => (
          <div key={row} className="flex gap-4 py-2">
            {[...Array(5)].map((_, col) => (
              <div key={col} className="shimmer h-4 flex-1 rounded-md" />
            ))}
          </div>
        ))}
      </div>
    </div>
  ),
};

export default function LoadingShimmer({
  width,
  height,
  variant = 'line',
  className = '',
  count = 1,
}) {
  const renderPreset = PRESETS[variant] || PRESETS.line;

  if (count <= 1) {
    return <div className={className}>{renderPreset(width, height)}</div>;
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {[...Array(count)].map((_, i) => (
        <div key={i}>{renderPreset(width, height)}</div>
      ))}
    </div>
  );
}
