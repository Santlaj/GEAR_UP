/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        gov: {
          navy: '#0B192C',
          dark: '#0f172a',
          header: '#0d1527',
          saffron: '#FF9933',
          green: '#138808',
          blue: '#1d4ed8',
          sky: '#0284c7',
          lightBg: '#f8fafc',
          border: '#e2e8f0',
        },
        status: {
          nonCompliant: '#dc2626',
          nonCompliantBg: '#fef2f2',
          nonCompliantBorder: '#fecaca',
          needsReview: '#d97706',
          needsReviewBg: '#fffbeb',
          needsReviewBorder: '#fde68a',
          compliant: '#16a34a',
          compliantBg: '#f0fdf4',
          compliantBorder: '#bbf7d0',
        }
      },
      fontFamily: {
        sans: ['Arial', 'Helvetica', 'sans-serif'],
        serif: ['Arial', 'Helvetica', 'sans-serif'],
        mono: ['Arial', 'Helvetica', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
