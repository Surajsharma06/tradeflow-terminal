const base = import.meta.env.VITE_API_URL ?? '';
export const API = base.endsWith('/') ? base.slice(0, -1) : base;
