import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useThemeStore = create(persist(
  (set) => ({
    theme: 'dark',
    toggle: () => set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      document.body.style.backgroundColor = next === 'light' ? '#eef2fa' : '#070812';
      return { theme: next };
    }),
    init: (theme) => {
      document.documentElement.setAttribute('data-theme', theme || 'dark');
      document.body.style.backgroundColor = theme === 'light' ? '#eef2fa' : '#070812';
    },
  }),
  { name: 'theme-pref' }
));

export default useThemeStore;
