import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useThemeStore = create(persist(
  (set) => ({
    theme: 'light',
    toggle: () => set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      document.body.style.backgroundColor = next === 'light' ? '#e8eee9' : '#0b0d0a';
      return { theme: next };
    }),
    init: (theme) => {
      const t = theme || 'light';
      document.documentElement.setAttribute('data-theme', t);
      document.body.style.backgroundColor = t === 'light' ? '#e8eee9' : '#0b0d0a';
    },
  }),
  {
    name: 'theme-pref',
    // Bump version to reset older visitors (who may have 'dark' saved) back
    // to the light default once. They can still toggle to dark afterwards.
    version: 1,
    migrate: (persisted) => ({ ...(persisted || {}), theme: 'light' }),
  }
));

export default useThemeStore;
