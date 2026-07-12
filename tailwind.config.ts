import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0B1220",
        panel: "#111827",
        panelLine: "#22304A",
        paper: "#F5F3EC",
        muted: "#8C97AD",
        "signal-accent": "#5B8DEF",
        "signal-pass": "#3FB68B",
        "signal-fail": "#D65A4A",
        "signal-warn": "#E8A33D",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        "mono-data": ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
