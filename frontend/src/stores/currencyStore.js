import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const RATES   = { USD: 1.0, INR: 85.0, CAD: 1.36 };
const SYMBOLS = { USD: '$', INR: '₹', CAD: 'C$' };

const useCurrencyStore = create(persist(
  (set, get) => ({
    currency: 'USD',
    setCurrency: (c) => set({ currency: c }),
    convert: (usd) => (usd ?? 0) * RATES[get().currency],
    format: (usd, decimals = 0) => {
      const val = (usd ?? 0) * RATES[get().currency];
      const sym = SYMBOLS[get().currency];
      if (Math.abs(val) >= 1_000_000) return `${sym}${(val / 1_000_000).toFixed(2)}M`;
      if (Math.abs(val) >= 1_000)     return `${sym}${(val / 1_000).toFixed(1)}K`;
      return `${sym}${val.toFixed(decimals)}`;
    },
    symbol: () => SYMBOLS[get().currency],
  }),
  { name: 'currency-pref' }
));

export default useCurrencyStore;
export { RATES, SYMBOLS };
