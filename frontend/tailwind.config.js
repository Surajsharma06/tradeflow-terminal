/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "SF Pro Display", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "Cascadia Code", "SF Mono", "monospace"],
      },
      colors: {
        bg:       "var(--color-bg)",
        "bg-alt": "var(--color-bg-alt)",
        surface: {
          DEFAULT:  "var(--color-surface)",
          elevated: "var(--color-surface-elevated)",
          hover:    "var(--color-surface-hover)",
          active:   "var(--color-surface-active)",
        },
        border: {
          DEFAULT: "var(--color-border)",
          light:   "var(--color-border-light)",
          focus:   "var(--color-border-focus)",
        },
        text: {
          primary:   "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          tertiary:  "var(--color-text-tertiary)",
          muted:     "var(--color-text-muted)",
        },
        positive: {
          DEFAULT: "var(--color-positive)",
          subtle:  "var(--color-positive-subtle)",
          strong:  "var(--color-positive-strong)",
        },
        negative: {
          DEFAULT: "var(--color-negative)",
          subtle:  "var(--color-negative-subtle)",
          strong:  "var(--color-negative-strong)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          subtle:  "var(--color-warning-subtle)",
        },
        accent: {
          DEFAULT: "var(--color-accent)",
          subtle:  "var(--color-accent-subtle)",
          hover:   "var(--color-accent-hover)",
          muted:   "var(--color-accent-muted)",
        },
        purple: {
          DEFAULT: "var(--color-purple)",
          subtle:  "var(--color-purple-subtle)",
        },
        gold: {
          DEFAULT: "var(--color-gold)",
          subtle:  "var(--color-gold-subtle)",
        },
        info: {
          DEFAULT: "var(--color-info)",
          subtle:  "var(--color-info-subtle)",
        },
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: {
        elevated:     "var(--shadow-elevated)",
        card:         "var(--shadow-card)",
        "glow-green": "var(--shadow-glow-green)",
        "glow-red":   "var(--shadow-glow-red)",
        "glow-blue":  "var(--shadow-glow-blue)",
        "glow-gold":  "var(--shadow-glow-gold)",
      },
      animation: {
        "fade-in":       "fade-in 0.3s ease-out",
        "slide-up":      "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
        "slide-in-right":"slide-in-right 0.3s ease-out",
        "pulse-glow":    "pulse-glow 2s ease-in-out infinite",
        shimmer:         "shimmer 2s linear infinite",
        "ticker-scroll": "ticker-scroll 30s linear infinite",
        "count-up":      "count-up 1s ease-out",
        "bounce-in":     "bounce-in 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)",
      },
    },
  },
  plugins: [],
}
