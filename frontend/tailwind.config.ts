import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Deep navy / charcoal base with cyan accents -- a security-console
        // palette rather than a consumer-app one.
        base: {
          950: "#060910",
          900: "#0a0f1a",
          850: "#0e1524",
          800: "#131c2e",
          700: "#1c2740",
          600: "#273451",
        },
        accent: {
          DEFAULT: "#22d3ee",
          soft: "#67e8f9",
          dim: "#0e7490",
        },
        ok: "#34d399",
        warn: "#fbbf24",
        danger: "#f87171",
        locked: "#a78bfa",
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,211,238,0.18), 0 8px 32px -8px rgba(34,211,238,0.22)",
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 12px 32px -16px rgba(0,0,0,0.8)",
      },
      keyframes: {
        "pulse-ring": {
          "0%": { transform: "scale(0.95)", opacity: "0.7" },
          "70%": { transform: "scale(1.15)", opacity: "0" },
          "100%": { transform: "scale(0.95)", opacity: "0" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 2.4s cubic-bezier(0.4,0,0.6,1) infinite",
        "slide-up": "slide-up 0.35s ease-out both",
        shimmer: "shimmer 1.8s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
