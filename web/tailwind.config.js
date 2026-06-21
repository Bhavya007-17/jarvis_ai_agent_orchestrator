export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: '#04070D',
        panel: '#0A121C',
        core: {
          DEFAULT: '#22D3EE',
          deep: '#0E7490',
          dim: '#155E75',
        },
      },
      fontFamily: {
        display: ['Orbitron', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        hud: ['"Share Tech Mono"', 'ui-monospace', 'monospace'],
        sans: ['Rajdhani', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 20px rgba(34, 211, 238, 0.35)',
        'glow-sm': '0 0 10px rgba(34, 211, 238, 0.30)',
        'glow-inset': 'inset 0 0 24px rgba(34, 211, 238, 0.06)',
      },
      keyframes: {
        'spin-slow': { to: { transform: 'rotate(360deg)' } },
        'spin-rev': { to: { transform: 'rotate(-360deg)' } },
        'core-pulse': {
          '0%, 100%': { opacity: '0.85', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.08)' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'spin-slow': 'spin-slow 18s linear infinite',
        'spin-rev': 'spin-rev 26s linear infinite',
        'core-pulse': 'core-pulse 3.2s ease-in-out infinite',
        scan: 'scan 7s linear infinite',
        'fade-up': 'fade-up 0.35s ease-out both',
      },
    },
  },
  plugins: [],
}
