/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        // Luxury Brand Colors
        brand: {
          red: "var(--color-brand-red)",
          green: "var(--color-brand-green)",
          "red-dark": "var(--color-brand-red-dark)",
          "green-dark": "var(--color-brand-green-dark)",
          "red-light": "var(--color-brand-red-light)",
          "green-light": "var(--color-brand-green-light)",
          yellow: "var(--color-brand-yellow)",
          "yellow-dark": "var(--color-brand-yellow-dark)",
          "yellow-light": "var(--color-brand-yellow-light)",
          dark: "var(--color-brand-dark)",
          navy: "var(--color-brand-navy)",
          "luxury-charcoal": "var(--color-luxury-charcoal)",
          gold: "var(--color-brand-gold)",
          "gold-dark": "var(--color-brand-gold-dark)",
          "gold-light": "var(--color-brand-gold-light)",
        },
        text: {
          primary: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          muted: "var(--color-text-muted)",
          luxury: "var(--color-text-luxury)",
        },
        bg: {
          primary: "var(--color-bg-primary)",
          alt: "var(--color-bg-alt)",
          warm: "var(--color-bg-warm)",
          glass: "var(--color-bg-glass)",
          dark: "var(--color-bg-dark)",
          navy: "var(--color-bg-navy)",
          charcoal: "var(--color-bg-charcoal)",
        },
        border: {
          light: "var(--color-border-light)",
          luxury: "var(--color-border-luxury)",
        },
        // shadcn/ui color system
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      backgroundImage: {
        "luxury-gradient": "var(--gradient-luxury)",
        "warm-gradient": "var(--gradient-warm)",
        "mesh-gradient": "var(--gradient-mesh)",
        "shimmer": "linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.2), transparent)",
      },
      boxShadow: {
        "glass": "var(--glass-shadow)",
        "luxury": "0 25px 50px -20px rgba(0, 0, 0, 0.1)",
        "luxury-hover": "0 30px 60px -20px rgba(0, 0, 0, 0.12)",
        "glow": "0 0 20px rgba(27, 67, 50, 0.3)",
        "glow-strong": "0 0 30px rgba(27, 67, 50, 0.5)",
      },
      backdropBlur: {
        "glass": "16px",
        "panel": "20px",
      },
      animation: {
        "fade-in-up": "fadeInUp 0.6s ease-out forwards",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
      },
      transitionTimingFunction: {
        "luxury": "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "Consolas", "monospace"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
