export type ThemeColorKey =
  | "background"
  | "foreground"
  | "card"
  | "cardForeground"
  | "cardStrong"
  | "popover"
  | "popoverForeground"
  | "muted"
  | "mutedForeground"
  | "border"
  | "input"
  | "primary"
  | "primaryForeground"
  | "secondary"
  | "secondaryForeground"
  | "accent"
  | "accentForeground"
  | "brand"
  | "brandForeground"
  | "destructive"
  | "destructiveForeground"
  | "success"
  | "successForeground"
  | "warning"
  | "warningForeground"
  | "info"
  | "infoForeground"
  | "ring"
  | "shadowColor"
  | "chartSaved"
  | "chartApplied"
  | "chartRecruiter"
  | "chartTech"
  | "chartFinal"
  | "chartOffer"
  | "chartRejected"
  | "chartWithdrawn"
  | "chartGhosted";

export type ThemeDefinition = {
  id: string;
  label: string;
  colors: Record<ThemeColorKey, string>;
};

const cssVariableNames: Record<ThemeColorKey, `--${string}`> = {
  background: "--background",
  foreground: "--foreground",
  card: "--card",
  cardForeground: "--card-foreground",
  cardStrong: "--card-strong",
  popover: "--popover",
  popoverForeground: "--popover-foreground",
  muted: "--muted",
  mutedForeground: "--muted-foreground",
  border: "--border",
  input: "--input",
  primary: "--primary",
  primaryForeground: "--primary-foreground",
  secondary: "--secondary",
  secondaryForeground: "--secondary-foreground",
  accent: "--accent",
  accentForeground: "--accent-foreground",
  brand: "--brand",
  brandForeground: "--brand-foreground",
  destructive: "--destructive",
  destructiveForeground: "--destructive-foreground",
  success: "--success",
  successForeground: "--success-foreground",
  warning: "--warning",
  warningForeground: "--warning-foreground",
  info: "--info",
  infoForeground: "--info-foreground",
  ring: "--ring",
  shadowColor: "--shadow-color",
  chartSaved: "--chart-saved",
  chartApplied: "--chart-applied",
  chartRecruiter: "--chart-recruiter",
  chartTech: "--chart-tech",
  chartFinal: "--chart-final",
  chartOffer: "--chart-offer",
  chartRejected: "--chart-rejected",
  chartWithdrawn: "--chart-withdrawn",
  chartGhosted: "--chart-ghosted"
};

export const themes = {
  sage: {
    id: "sage",
    label: "Muted Sage",
    colors: {
      background: "#F5FAF4",
      foreground: "#132116",
      card: "#EEF7EC",
      cardForeground: "#132116",
      cardStrong: "#FFFFFF",
      popover: "#FFFFFF",
      popoverForeground: "#132116",
      muted: "#E4F0E1",
      mutedForeground: "#5B695A",
      border: "#C8DCC4",
      input: "#FCFEFB",
      primary: "#2F6A3A",
      primaryForeground: "#FFFFFF",
      secondary: "#EAF4E7",
      secondaryForeground: "#263D29",
      accent: "#D8EDD5",
      accentForeground: "#2B5631",
      brand: "#7FB377",
      brandForeground: "#132116",
      destructive: "#A2474C",
      destructiveForeground: "#FFFFFF",
      success: "#D8EDD5",
      successForeground: "#2F6A3A",
      warning: "#F0E3C8",
      warningForeground: "#6D4F20",
      info: "#D6EBE4",
      infoForeground: "#315F55",
      ring: "#7FB377",
      shadowColor: "#3A6F32",
      chartSaved: "#7FB377",
      chartApplied: "#5F9E87",
      chartRecruiter: "#6A9B77",
      chartTech: "#4F8A62",
      chartFinal: "#789F62",
      chartOffer: "#3A6F32",
      chartRejected: "#A15A5F",
      chartWithdrawn: "#A07B4A",
      chartGhosted: "#697665"
    }
  }
} satisfies Record<string, ThemeDefinition>;

export type ThemeId = keyof typeof themes;

export const defaultThemeId: ThemeId = "sage";

export function hexToHslTriplet(hex: string) {
  const raw = hex.replace("#", "").trim();
  const normalized =
    raw.length === 3
      ? raw
          .split("")
          .map((value) => value + value)
          .join("")
      : raw;

  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
    throw new Error(`Invalid hex color: ${hex}`);
  }

  const value = Number.parseInt(normalized, 16);
  const red = ((value >> 16) & 255) / 255;
  const green = ((value >> 8) & 255) / 255;
  const blue = (value & 255) / 255;
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const lightness = (max + min) / 2;
  let hue = 0;
  let saturation = 0;

  if (max !== min) {
    const delta = max - min;
    saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min);

    if (max === red) {
      hue = (green - blue) / delta + (green < blue ? 6 : 0);
    } else if (max === green) {
      hue = (blue - red) / delta + 2;
    } else {
      hue = (red - green) / delta + 4;
    }

    hue /= 6;
  }

  return `${Math.round(hue * 360)} ${Math.round(saturation * 100)}% ${Math.round(lightness * 100)}%`;
}

export function themeToCssVariables(theme: ThemeDefinition) {
  return Object.entries(theme.colors).reduce<Record<string, string>>((variables, [key, hex]) => {
    variables[cssVariableNames[key as ThemeColorKey]] = hexToHslTriplet(hex);
    return variables;
  }, {});
}
