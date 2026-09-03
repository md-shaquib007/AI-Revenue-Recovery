/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#090d16",
        foreground: "#f8fafc",
        card: "#0f172a",
        border: "#1e293b",
        razorpay: {
          blue: "#3395ff",
          dark: "#0b192c",
          accent: "#528ff0",
          emerald: "#10b981",
        },
      },
    },
  },
  plugins: [],
};
