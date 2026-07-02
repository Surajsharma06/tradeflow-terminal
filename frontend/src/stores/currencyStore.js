import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Rates are expressed as 1 USD = X units of currency.
const RATES   = { USD: 1.0, INR: 85.0, CAD: 1.36 };
const SYMBOLS = { USD: '$', INR: '₹', CAD: 'C$' };
const LOCALES = { USD: 'en-US', INR: 'en-IN', CAD: 'en-CA' };

const useCurrencyStore = create(persist(
  (set, get) => ({
    currency: 'USD',
    setCurrency: (c) => set({ currency: c }),

    // Convert a USD amount into the selected currency.
    convert: (usd) => (usd ?? 0) * RATES[get().currency],

    // Convert an amount quoted in `nativeCurrency` into the selected currency.
    convertFrom: (value, nativeCurrency = 'USD') => {
      const usd = (value ?? 0) / (RATES[nativeCurrency] ?? 1);
      return usd * RATES[get().currency];
    },

    // Format a USD amount in the selected currency with K/M abbreviation.
    format: (usd, decimals = 0) => {
      const val = (usd ?? 0) * RATES[get().currency];
      const sym = SYMBOLS[get().currency];
      if (Math.abs(val) >= 1_000_000) return `${sym}${(val / 1_000_000).toFixed(2)}M`;
      if (Math.abs(val) >= 1_000)     return `${sym}${(val / 1_000).toFixed(1)}K`;
      return `${sym}${val.toFixed(decimals)}`;
    },

    // Format an amount quoted in `nativeCurrency`, converted to the selected
    // currency, with locale-aware thousand separators (full precision).
    formatFrom: (value, nativeCurrency = 'USD', decimals = 2) => {
      const cur = get().currency;
      const usd = (value ?? 0) / (RATES[nativeCurrency] ?? 1);
      const val = usd * RATES[cur];
      return `${SYMBOLS[cur]}${val.toLocaleString(LOCALES[cur], {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}`;
    },

    symbol: () => SYMBOLS[get().currency],
  }),
  { name: 'currency-pref' }
));

export default useCurrencyStore;
export { RATES, SYMBOLS, LOCALES };
