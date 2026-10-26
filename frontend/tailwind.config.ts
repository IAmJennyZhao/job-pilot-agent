import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      maxWidth: {
        workspace: "88rem"
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
          strong: "hsl(var(--card-strong))"
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))"
        },
        muted: "hsl(var(--muted))",
        "muted-foreground": "hsl(var(--muted-foreground))",
        primary: "hsl(var(--primary))",
        "primary-foreground": "hsl(var(--primary-foreground))",
        sidebar: "hsl(var(--sidebar))",
        secondary: "hsl(var(--secondary))",
        "secondary-foreground": "hsl(var(--secondary-foreground))",
        accent: "hsl(var(--accent))",
        "accent-foreground": "hsl(var(--accent-foreground))",
        brand: "hsl(var(--brand))",
        "brand-foreground": "hsl(var(--brand-foreground))",
        destructive: "hsl(var(--destructive))",
        "destructive-foreground": "hsl(var(--destructive-foreground))",
        success: "hsl(var(--success))",
        "success-foreground": "hsl(var(--success-foreground))",
        warning: "hsl(var(--warning))",
        "warning-foreground": "hsl(var(--warning-foreground))",
        info: "hsl(var(--info))",
        "info-foreground": "hsl(var(--info-foreground))",
        chart: {
          saved: "hsl(var(--chart-saved))",
          applied: "hsl(var(--chart-applied))",
          recruiter: "hsl(var(--chart-recruiter))",
          tech: "hsl(var(--chart-tech))",
          final: "hsl(var(--chart-final))",
          offer: "hsl(var(--chart-offer))",
          rejected: "hsl(var(--chart-rejected))",
          withdrawn: "hsl(var(--chart-withdrawn))",
          ghosted: "hsl(var(--chart-ghosted))"
        },
        status: {
          saved: "hsl(var(--chart-saved))",
          applied: "hsl(var(--chart-applied))",
          recruiter: "hsl(var(--chart-recruiter))",
          tech: "hsl(var(--chart-tech))",
          final: "hsl(var(--chart-final))",
          offer: "hsl(var(--chart-offer))",
          rejected: "hsl(var(--chart-rejected))",
          withdrawn: "hsl(var(--chart-withdrawn))",
          ghosted: "hsl(var(--chart-ghosted))"
        }
      },
      boxShadow: {
        panel: "0 10px 30px hsl(var(--shadow-color) / 0.08), 0 1px 2px hsl(var(--shadow-color) / 0.06)"
      }
    }
  },
  plugins: []
};

export default config;

