/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--success-foreground))'
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))'
        },
        ocean: {
          deep: 'hsl(var(--ocean-deep))',
          mid: 'hsl(var(--ocean-mid))',
          surface: 'hsl(var(--ocean-surface))'
        },
        neural: {
          cyan: 'hsl(var(--neural-cyan))',
          teal: 'hsl(var(--neural-teal))',
          purple: 'hsl(var(--neural-purple))',
          blue: 'hsl(var(--neural-blue))',
          pink: 'hsl(var(--neural-pink))'
        }
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)'
      },
      boxShadow: {
        glow: 'var(--shadow-glow-md)',
        'glow-sm': 'var(--shadow-glow-sm)',
        'glow-lg': 'var(--shadow-glow-lg)',
        card: 'var(--shadow-card)'
      },
      fontFamily: {
        display: ['var(--font-display)'],
        mono: ['var(--font-mono)']
      },
      animation: {
        shimmer: 'shimmer 2.5s infinite linear',
        'pulse-glow': 'pulseGlow 4s ease-in-out infinite',
        'float-orb': 'floatOrb 12s ease-in-out infinite',
        'neural-pulse': 'neuralPulse 3s ease-in-out infinite'
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' }
        },
        pulseGlow: {
          '0%, 100%': { opacity: '0.45', transform: 'scale(1)' },
          '50%': { opacity: '0.75', transform: 'scale(1.04)' }
        },
        floatOrb: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%': { transform: 'translate(12px, -18px) scale(1.05)' },
          '66%': { transform: 'translate(-8px, 10px) scale(0.97)' }
        },
        neuralPulse: {
          '0%, 100%': { opacity: '0.35' },
          '50%': { opacity: '0.65' }
        }
      }
    }
  },
  plugins: []
};
