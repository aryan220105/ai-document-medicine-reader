/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12201c",
        mist: "#e8f0ec",
        leaf: "#0d6b5c",
        leafdark: "#0a4f44",
        pine: "#163f38",
        foam: "#f7fbf9",
        coral: "#c45c3a",
        softline: "#c9d9d2",
      },
      fontFamily: {
        sans: ["Outfit", "Segoe UI", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      boxShadow: {
        soft: "0 18px 40px -28px rgba(18, 32, 28, 0.35)",
        lift: "0 10px 28px -18px rgba(13, 107, 92, 0.35)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        rise: "rise 0.55s ease-out both",
        "pulse-soft": "pulseSoft 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
