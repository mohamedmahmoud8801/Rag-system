/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--background) / <alpha-value>)",
        sidebar: "rgb(var(--sidebar) / <alpha-value>)",
        card: "rgb(var(--card) / <alpha-value>)",
        elevated: "rgb(var(--elevated) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        foreground: "rgb(var(--foreground) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        primary: { DEFAULT: "rgb(var(--primary) / <alpha-value>)", soft: "rgb(var(--primary-soft) / <alpha-value>)" },
        success: "rgb(var(--success) / <alpha-value>)",
        warning: "rgb(var(--warning) / <alpha-value>)",
        danger: "rgb(var(--danger) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["'Geist Variable'", "'IBM Plex Sans Arabic'", "ui-sans-serif", "system-ui", "sans-serif"],
        arabic: ["'IBM Plex Sans Arabic'", "'Geist Variable'", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { xl: "0.9rem", "2xl": "1.1rem" },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
        pulse3: { "0%, 80%, 100%": { opacity: ".25" }, "40%": { opacity: "1" } },
      },
      animation: { "fade-in": "fade-in .25s ease-out both", pulse3: "pulse3 1.2s infinite ease-in-out" },
    },
  },
  plugins: [],
};
