import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0A0A0A",
        paper: "#FFFFFF",
        mist: "#F3F2EF",
        line: "#DCDAD4",
        faint: "#8A877F",
        signal: "#7A1F1F",
      },
      fontFamily: {
        display: ["\"Cormorant Garamond\"", "Georgia", "serif"],
        body: ["Inter", "system-ui", "sans-serif"],
      },
      letterSpacing: { micro: "0.14em" },
    },
  },
  plugins: [],
};
export default config;
