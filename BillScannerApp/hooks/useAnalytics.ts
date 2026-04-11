/**
 * hooks/useAnalytics.ts
 *
 * Fetches the analytics summary for a device.
 *
 * API shapes supported:
 *   GET /analytics/summary/{device_id}
 *   GET /analytics/summary?device_id={id}
 */

import { useState, useCallback } from "react";
import { API_ROUTES } from "@/constants/api";
import { AnalyticsSummary } from "@/types";

interface UseAnalyticsReturn {
  summary: AnalyticsSummary | null;
  loading: boolean;
  error:   string | null;
  refresh: () => Promise<void>;
}

/** Empty summary so components never crash on null array access */
const EMPTY_SUMMARY: AnalyticsSummary = {
  total_spend:  0,
  bill_count:   0,
  by_category:  [],
  by_store:     [],
  by_day:       [],
  by_month:     [],
  by_year:      [],
};

export function useAnalytics(deviceId: string): UseAnalyticsReturn {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    const pathUrl = API_ROUTES.analytics.summaryByPath(deviceId);
    const queryUrl = API_ROUTES.analytics.summaryByQuery(deviceId);
    console.log("[useAnalytics] GET", pathUrl);

    try {
      let res = await fetch(pathUrl);
      if (res.status === 404) {
        console.log("[useAnalytics] path route not found, trying query route");
        res = await fetch(queryUrl);
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status} – ${text}`);
      }

      const json = await res.json();
      console.log(
        `[useAnalytics] total_spend=${json.total_spend}  bill_count=${json.bill_count}`
      );

      // Merge with empty summary so missing keys never cause crashes
      setSummary({ ...EMPTY_SUMMARY, ...json });
    } catch (err: any) {
      console.error("[useAnalytics] fetch error:", err);
      setError(err?.message || "Failed to load analytics");
      // Keep last good summary visible rather than blanking the screen
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  return { summary, loading, error, refresh };
}
