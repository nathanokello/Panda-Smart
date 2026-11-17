/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        forest: '#0E3A1E',   // Deep Forest Green - headings, sidebar
        sprout: '#599827',   // Sprout Green - primary buttons, active states
        lime: '#8AC43E',     // Fresh Lime - highlights, progress
        emerald: '#24692C',  // Emerald Leaf - supporting accents
        mist: '#F5F8F4',     // Soft Mist - app background
        sage: '#DCE6D9',     // Sage Border
        charcoal: '#1E2922', // Slate Charcoal - body text
        moss: '#5C6E62',     // Muted Moss - secondary text
        success: '#2E8B57',
        warn: '#E59A24',
        danger: '#D64545',
        info: '#2B7A9E',
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
