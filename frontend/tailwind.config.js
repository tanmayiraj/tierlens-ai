/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          100: 'var(--color-brand-100)',
          500: 'var(--color-brand-500)',
          600: 'var(--color-brand-600)',
        },
        surface: {
          DEFAULT: 'var(--color-surface)',
          raised: 'var(--color-surface-raised)',
        },
        appBg: 'var(--color-bg)',
        appBorder: 'var(--color-border)',
        appText: {
          DEFAULT: 'var(--color-text)',
          muted: 'var(--color-text-muted)',
          faint: 'var(--color-text-faint)',
        },
        risk: {
          low: 'var(--risk-low)',
          'low-bg': 'var(--risk-low-bg)',
          'low-text': 'var(--risk-low-text)',
          medium: 'var(--risk-medium)',
          'medium-bg': 'var(--risk-medium-bg)',
          'medium-text': 'var(--risk-medium-text)',
          high: 'var(--risk-high)',
          'high-bg': 'var(--risk-high-bg)',
          'high-text': 'var(--risk-high-text)',
          critical: 'var(--risk-critical)',
          'critical-bg': 'var(--risk-critical-bg)',
          'critical-text': 'var(--risk-critical-text)',
        },
        tier: {
          0: 'var(--tier-0)',
          1: 'var(--tier-1)',
          2: 'var(--tier-2)',
          3: 'var(--tier-3)',
          4: 'var(--tier-4)',
        },
        simulated: {
          DEFAULT: 'var(--color-simulated)',
          bg: 'var(--color-simulated-bg)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
