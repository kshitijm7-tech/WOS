/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12161C",       // primary dark surface (nav, footer, hero)
        paper: "#F7F8FA",     // light workspace background
        slate: {
          DEFAULT: "#5B6472",
          light: "#8A93A3",
          dark: "#333B47",
        },
        amber: {
          DEFAULT: "#E8A33D",  // signal accent — attention / in-progress
          soft: "#FBEBD2",
        },
        teal: {
          DEFAULT: "#1E7F79",  // healthy / resolved states
          soft: "#DCEFEC",
        },
        alert: {
          DEFAULT: "#C1443C",  // denial / high risk
          soft: "#F6DEDC",
        },
        line: "#E4E7EC",
      },
      fontFamily: {
        display: ["\"Space Grotesk\"", "sans-serif"],
        body: ["\"Inter\"", "sans-serif"],
        mono: ["\"IBM Plex Mono\"", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(18,22,28,0.04), 0 1px 12px rgba(18,22,28,0.04)",
      },
    },
  },
  plugins: [],
};
