import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Seeded notifications — in production these arrive via websocket/API.
const SEED = [
  {
    id: 'n-1',
    type: 'signal',
    title: 'New BUY signal — AUD/USD',
    body: 'BB+RSI Oversold triggered at 0.68961 · 87% confidence',
    time: Date.now() - 4 * 60 * 1000,
  },
  {
    id: 'n-2',
    type: 'risk',
    title: 'Daily loss limit at 40%',
    body: 'You have used 1.2% of your 3.0% daily loss budget.',
    time: Date.now() - 32 * 60 * 1000,
  },
  {
    id: 'n-3',
    type: 'signal',
    title: 'SELL signal closed — USD/CAD',
    body: 'Take-profit hit at 1.41400 · +1.9R',
    time: Date.now() - 2 * 60 * 60 * 1000,
  },
  {
    id: 'n-4',
    type: 'system',
    title: 'Backtest completed',
    body: '6-month SMC walk-forward finished — view results in Analytics.',
    time: Date.now() - 5 * 60 * 60 * 1000,
  },
];

const useNotificationStore = create(persist(
  (set, get) => ({
    notifications: SEED,
    readIds: [],

    unreadCount: () =>
      get().notifications.filter((n) => !get().readIds.includes(n.id)).length,

    markRead: (id) =>
      set((s) => ({
        readIds: s.readIds.includes(id) ? s.readIds : [...s.readIds, id],
      })),

    markAllRead: () =>
      set((s) => ({ readIds: s.notifications.map((n) => n.id) })),

    add: (notif) =>
      set((s) => ({
        notifications: [
          { id: `n-${Date.now()}`, time: Date.now(), ...notif },
          ...s.notifications,
        ].slice(0, 50),
      })),

    clear: () => set({ notifications: [], readIds: [] }),
  }),
  {
    name: 'notifications',
    // Persist read state only; notifications re-seed on fresh load.
    partialize: (s) => ({ readIds: s.readIds }),
  }
));

export default useNotificationStore;
