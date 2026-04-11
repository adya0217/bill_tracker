/**
 * constants/api.ts
 *
 * Central place for API configuration and the shared colour palette.
 *
 * API URL selection order:
 * 1) EXPO_PUBLIC_API_BASE_URL (recommended explicit override)
 * 2) Auto-detect host from Expo runtime (works for emulator + physical devices)
 * 3) Safe platform defaults
 */
import Constants from "expo-constants";
import { Platform } from "react-native";

const DEV_PORT = "8000";

function inferExpoHost(): string | null {
  const hostUri = Constants.expoConfig?.hostUri ?? null;
  if (!hostUri) return null;

  // hostUri examples:
  // - "192.168.1.22:8081"
  // - "localhost:8081"
  const host = hostUri.split(":")[0];
  if (!host) return null;

  // Android emulator must map host loopback to 10.0.2.2
  if (Platform.OS === "android" && host === "localhost") {
    return `http://10.0.2.2:${DEV_PORT}`;
  }
  return `http://${host}:${DEV_PORT}`;
}

function getApiBaseUrl(): string {
  const envUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (envUrl) return envUrl.replace(/\/+$/, "");

  const inferred = inferExpoHost();
  if (inferred) return inferred;

  if (Platform.OS === "android") return `http://10.0.2.2:${DEV_PORT}`;
  return `http://localhost:${DEV_PORT}`;
}

export const API_BASE_URL = getApiBaseUrl();
export const API_PREFIX = "/api/v1";

function withApiPrefix(path: string): string {
  const normalisedPath = path.startsWith("/") ? path : `/${path}`;
  const base = API_BASE_URL.endsWith(API_PREFIX)
    ? API_BASE_URL.slice(0, -API_PREFIX.length)
    : API_BASE_URL;
  return `${base}${API_PREFIX}${normalisedPath}`;
}

export const API_ROUTES = {
  bills: {
    upload: () => withApiPrefix("/bills/upload/"),
    byDevice: (deviceId: string, skip?: number, limit?: number) => {
      const query = new URLSearchParams();
      if (typeof skip === "number") query.set("skip", String(skip));
      if (typeof limit === "number") query.set("limit", String(limit));
      const suffix = query.toString() ? `?${query.toString()}` : "";
      return withApiPrefix(`/bills/device/${encodeURIComponent(deviceId)}${suffix}`);
    },
    byId: (billId: number) => withApiPrefix(`/bills/${billId}`),
  },
  analytics: {
    summaryByPath: (deviceId: string) =>
      withApiPrefix(`/analytics/summary/${encodeURIComponent(deviceId)}`),
    summaryByQuery: (deviceId: string) =>
      withApiPrefix(`/analytics/summary?device_id=${encodeURIComponent(deviceId)}`),
  },
  auth: {
    registerDevice: () => withApiPrefix("/auth/register-device"),
    validateDevice: (deviceId: string) =>
      withApiPrefix(`/auth/validate-device/${encodeURIComponent(deviceId)}`),
    deviceById: (deviceId: string) =>
      withApiPrefix(`/auth/device/${encodeURIComponent(deviceId)}`),
  },
  vendors: {
    list: () => withApiPrefix("/vendors/"),
    byId: (vendorId: number) => withApiPrefix(`/vendors/${vendorId}`),
  },
} as const;

// Must be valid hex/octal to pass backend device_id validation.
// Replace with a registered/stored device ID in production.
export const DEVICE_ID = "a1b2c3d4";

// ─────────────────────────────────────────────
// COLOUR PALETTE
// Used across all components so that a single change here
// updates the whole app.
// ─────────────────────────────────────────────
export const COLORS = {
  // Brand
  primary:       "#3b82f6",   // blue-500
  primaryDark:   "#1d4ed8",   // blue-700

  // Neutrals
  white:         "#ffffff",
  veryLightGray: "#f3f4f6",   // gray-100  – screen backgrounds
  lightGray:     "#e5e7eb",   // gray-200  – dividers, bar tracks
  gray:          "#6b7280",   // gray-500  – subtitles, secondary text
  darkGray:      "#374151",   // gray-700  – body text, item names
  dark:          "#111827",   // gray-900  – primary text, headings

  // Semantic
  success:       "#22c55e",   // green-500
  warning:       "#f59e0b",   // amber-500
  danger:        "#ef4444",   // red-500
} as const;

export type ColorKey = keyof typeof COLORS;

// Shared category helpers used by frontend utilities.
export const CATEGORY_KEYWORDS: Record<string, string[]> = {
  Groceries: ["milk", "bread", "rice", "atta", "dal", "egg", "vegetable", "fruit", "curd", "oil", "sugar"],
  Household: ["soap", "detergent", "shampoo", "cleaner", "brush", "tissue", "mop", "floor"],
  Medical: ["tablet", "medicine", "capsule", "syrup", "ointment", "vitamin", "paracetamol"],
  Electronics: ["charger", "cable", "usb", "adapter", "battery", "headphone", "led", "bulb"],
  Dining: ["pizza", "burger", "coffee", "tea", "meal", "thali", "sandwich", "biryani"],
  Beverages: ["cola", "pepsi", "coke", "sprite", "fanta", "soda", "lassi", "juice", "water"],
  Snacks: ["chips", "biscuit", "namkeen", "wafer", "kurkure", "chocolate", "candy"],
  Other: [],
};

export const CATEGORY_COLORS: Record<string, string> = {
  Groceries: COLORS.success,
  Household: "#06b6d4",
  Medical: "#f43f5e",
  Electronics: "#8b5cf6",
  Dining: "#f59e0b",
  Beverages: "#0ea5e9",
  Snacks: "#ec4899",
  Other: COLORS.gray,
};
