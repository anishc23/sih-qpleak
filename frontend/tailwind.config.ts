import type { Config } from "tailwindcss";

/**
 * SecureLock — the custody register.
 *
 * Every colour is named for an object in the physical chain of custody an
 * examination paper already travels through: the ruled register sheet it is
 * signed out of, the lac seal pressed on the packet, the verdigris on the
 * countersign stamp, iron-gall ink. The ground is ledger paper -- greenish
 * grey, the colour of a book that is written in, not one that is sent.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces, lightest-held-highest.
        register: "#E3E7DB", // page ground: the ruled ledger sheet
        leaf: "#EDF0E5", // a slip laid on the register
        sunk: "#D6DBCB", // recessed: table zebra, meters, wells
        rule: {
          DEFAULT: "#BEC4B0", // hairlines and column rules
          soft: "#CCD2BF",
        },

        // Iron-gall ink, stepped down. Every step clears 4.5:1 on `register`
        // so there is no such thing as an illegible hint in this system.
        ink: {
          DEFAULT: "#171B16",
          2: "#2E332C",
          3: "#454B41",
          4: "#545A4F",
          5: "#5C6257",
          6: "#5F6560",
        },

        // Sealing wax. Reserved for the sealed state and the one primary
        // action per screen -- if it is red, something is shut.
        lac: {
          DEFAULT: "#8E3020",
          soft: "#A84232",
        },

        // Legacy semantic names kept so status logic reads unchanged.
        accent: {
          DEFAULT: "#8E3020",
          soft: "#A84232",
          dim: "#6E2418",
        },
        ok: "#2E5C4E", // verdigris: verified, released, confirmed on chain
        warn: "#7D560F", // ochre: pending, under review
        danger: "#9B1C1C", // failure and tamper -- bluer than lac, never confused
        locked: "#8E3020", // sealed is lac, always
      },
      fontFamily: {
        // Eczar: drawn for scholarly publishing in India, Latin + Devanagari
        // from one family. Reads as a printed examination cover.
        display: ["var(--font-display)", "Georgia", "serif"],
        // Archivo: a grotesque drawn for print forms. Holds at 12px in the
        // dense tables that are most of this application.
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        // Spline Sans Mono: even colour across 64 characters, so a SHA-256
        // reads as a woven band rather than noise. 0/O and 1/l stay apart.
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        // Deboss, not glow. Paper is pressed, it does not emit light.
        deboss: "inset 0 1px 0 0 rgba(255,255,255,0.7), 0 1px 0 0 rgba(25,29,24,0.06)",
        seal: "0 2px 0 0 rgba(25,29,24,0.18)",
      },
      keyframes: {
        "slide-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "slide-up": "slide-up 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
