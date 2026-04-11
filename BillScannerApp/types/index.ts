/**
 * types/index.ts
 *
 * Single source of truth for all shared TypeScript types.
 * Keep field names in sync with the backend schemas.py.
 */

// ─────────────────────────────────────────────
// BILL TYPES
// ─────────────────────────────────────────────

/** One line item on a scanned bill. */
export interface BillItem {
  /** Display name – preferred field */
  name:         string;
  /** Same as name – DB column name, kept for backend compat */
  product_name: string;
  sku:          string;
  quantity:     number;
  unit_price:   number;
  total_price:  number;
  tax:          number;
  category:     string;
}

/** Full structured bill returned by the upload / detail endpoints. */
export interface StructuredBill {
  id?:          number;
  merchant:     string;
  area?:        string;
  bill_date:    string;        // YYYY-MM-DD or ""
  bill_number:  string | null; // receipt / invoice number from OCR
  subtotal:     number;
  tax:          number;
  total_amount: number;
  items:        BillItem[];
  pipeline?:    "llm" | "heuristic"; // which parsing path was used
}

/** Summary row shown in the bills list (no line items). */
export interface BillListItem {
  id:           number;
  merchant:     string;
  area?:        string | null;
  bill_date:    string | null;
  bill_number?: string | null;
  total_amount: number;
  created_at:   string | null;
}

/** Computed per-category spend breakdown for a single bill. */
export interface CategoryBreakdown {
  /** Map of category name → total spend */
  categoryTotals: Record<string, number>;
  /** Sum of all item totals */
  totalSpend:     number;
  /** Highest single-category value (used for bar scaling) */
  maxTotal:       number;
}

// ─────────────────────────────────────────────
// ANALYTICS TYPES
// ─────────────────────────────────────────────

export interface CategoryStat {
  category:    string;
  total_spend: number;
  bill_count?: number;
}

export interface StoreStat {
  store:       string;
  total_spend: number;
  bill_count?: number;
}

export interface DayStat {
  date:        string;   // YYYY-MM-DD
  total_spend: number;
  bill_count:  number;
}

export interface MonthStat {
  month:       string;   // YYYY-MM
  total_spend: number;
  bill_count?: number;
}

export interface YearStat {
  year:        string;   // YYYY
  total_spend: number;
  bill_count?: number;
}

export type FilterType = "today" | "week" | "month" | "year" | "all";

export interface DateRange {
  startDate: Date;
  endDate: Date;
}

/** Full analytics summary returned by GET /analytics/summary/{device_id} */
export interface AnalyticsSummary {
  total_spend: number;
  bill_count:  number;
  by_category: CategoryStat[];
  by_store:    StoreStat[];
  by_day:      DayStat[];
  by_month:    MonthStat[];
  by_year:     YearStat[];
}
