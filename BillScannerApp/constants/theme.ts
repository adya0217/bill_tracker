/**
 * constants/theme.ts
 *
 * Provides the `Colors` object used by the tab navigator for
 * active tint colours in light / dark mode.
 *
 * Kept separate from api.ts so the navigation theme stays isolated
 * from the rest of the palette.
 */

export const Colors = {
  light: {
    tint:            "#3b82f6",   // matches COLORS.primary
    background:      "#ffffff",
    tabIconDefault:  "#9ca3af",
    tabIconSelected: "#3b82f6",
    text:            "#111827",
  },
  dark: {
    tint:            "#60a5fa",   // blue-400 – lighter for dark backgrounds
    background:      "#111827",
    tabIconDefault:  "#6b7280",
    tabIconSelected: "#60a5fa",
    text:            "#f9fafb",
  },
} as const;
