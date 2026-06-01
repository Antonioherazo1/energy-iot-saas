/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1f2933",
        panel: "#f6f8fb",
        line: "#d8dee8",
        brand: "#0f766e",
        accent: "#2563eb"
      }
    }
  },
  plugins: []
};

