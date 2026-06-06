import type { Config } from "tailwindcss"

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: "#0d1625",
        surface2: "#111d30",
        "border-subtle": "#1a2840",
        "text-dim": "#4a6080",
        "status-yes": "#10b981",
        "status-no": "#f43f5e",
        "status-maybe": "#f59e0b",
        accent: "#3b82f6",
      },
    },
  },
  plugins: [],
}

export default config
