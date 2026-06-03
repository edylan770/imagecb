/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /** Tista navy — headers, sidebar chrome, dark UI */
        navy: {
          50: "#f4f7fb",
          100: "#e2e9f3",
          200: "#c5d4e8",
          300: "#94aed0",
          400: "#5f84b0",
          500: "#3d6394",
          600: "#2d4d78",
          700: "#1f3a5c",
          800: "#152a45",
          900: "#0b1f3a",
          950: "#071525",
        },
        /** Tista medium blue — primary actions, links, accents */
        brand: {
          50: "#eef5fc",
          100: "#d6e8f8",
          200: "#aed0f0",
          300: "#7ab3e3",
          400: "#4a94d4",
          500: "#2b7bc4",
          600: "#2368a8",
          700: "#1d5589",
          800: "#18456f",
          900: "#133a5c",
        },
        tista: {
          navy: "#0b1f3a",
          blue: "#2b7bc4",
          black: "#111111",
          white: "#ffffff",
        },
      },
      fontFamily: {
        sans: [
          "Segoe UI",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
