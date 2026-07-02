import { useEffect, useRef, useState } from 'react';

/**
 * Displays a price that flashes green/red when its value changes,
 * the way professional trading terminals do. Flashes are debounced
 * (min 300ms apart) so rapid ticks don't strobe unreadably.
 */
export default function AnimatedPrice({ value, format = (v) => v, className = '' }) {
  const prev = useRef(value);
  const lastFlash = useRef(0);
  const [flash, setFlash] = useState(null); // 'up' | 'down' | null

  useEffect(() => {
    if (value === prev.current) return;
    const dir = value > prev.current ? 'up' : 'down';
    prev.current = value;

    const now = Date.now();
    if (now - lastFlash.current < 300) return; // debounce
    lastFlash.current = now;

    setFlash(dir);
    const id = setTimeout(() => setFlash(null), 500);
    return () => clearTimeout(id);
  }, [value]);

  return (
    <span
      className={`transition-colors duration-500 rounded px-0.5 -mx-0.5 ${
        flash === 'up'
          ? 'text-positive bg-positive-subtle'
          : flash === 'down'
            ? 'text-negative bg-negative-subtle'
            : ''
      } ${className}`}
    >
      {format(value)}
    </span>
  );
}
