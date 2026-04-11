/**
 * hooks/use-color-scheme.ts
 *
 * Thin wrapper so the rest of the app imports from @/hooks/use-color-scheme
 * rather than directly from react-native.  This makes it easy to add
 * a manual override (e.g. user preference stored in AsyncStorage) later.
 */

import { useColorScheme as _useColorScheme } from "react-native";

export function useColorScheme(): "light" | "dark" {
  const scheme = _useColorScheme();
  // Default to light if the system hasn't reported a preference yet
  return scheme === "dark" ? "dark" : "light";
}
