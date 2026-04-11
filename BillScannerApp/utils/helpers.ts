/**
 * Utility functions
 */

import { CATEGORY_KEYWORDS, CATEGORY_COLORS, COLORS } from "@/constants/api";
import {
  BillItem,
  CategoryBreakdown,
  StructuredBill,
  DateRange,
  FilterType,
} from "@/types";

/**
 * Categorize an item based on its name
 */
export function categorizeItem(name: string): string {
  const nameLower = name.toLowerCase();

  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    if (keywords.some((keyword) => nameLower.includes(keyword))) {
      return category;
    }
  }

  return "Other";
}

/**
 * Calculate category breakdown for a bill
 */
export function computeCategoryBreakdown(
  bill: StructuredBill | null
): CategoryBreakdown {
  const categoryTotals: Record<string, number> = {};
  let totalSpend = 0;

  if (!bill?.items) {
    return { categoryTotals, maxTotal: 0, totalSpend: 0 };
  }

  bill.items.forEach((item) => {
    const qty = Number(item.quantity || 1);
    const unitPrice = Number(item.unit_price || 0);
    const lineTotal = Number(item.total_price || qty * unitPrice);
    const cat = item.category ?? categorizeItem(item.name);

    categoryTotals[cat] = (categoryTotals[cat] || 0) + lineTotal;
    totalSpend += lineTotal;
  });

  const maxTotal = Object.values(categoryTotals).reduce(
    (max, v) => (v > max ? v : max),
    0
  );

  return { categoryTotals, maxTotal, totalSpend };
}

/**
 * Get color for a category
 */
export function getCategoryColor(category: string): string {
  return CATEGORY_COLORS[category] || COLORS.gray;
}

/**
 * Format currency
 */
export function formatCurrency(amount: number): string {
  return `₹${amount.toFixed(2)}`;
}

/**
 * Get date range for filter
 */
export function getDateRangeForFilter(filterType: FilterType): DateRange {
  const endDate = new Date();
  const startDate = new Date();

  switch (filterType) {
    case "today":
      startDate.setHours(0, 0, 0, 0);
      endDate.setHours(23, 59, 59, 999);
      break;
    case "week":
      startDate.setDate(endDate.getDate() - 7);
      break;
    case "month":
      startDate.setMonth(endDate.getMonth() - 1);
      break;
    case "year":
      startDate.setFullYear(endDate.getFullYear() - 1);
      break;
    case "all":
    default:
      startDate.setFullYear(1900); // Far past
      break;
  }

  return { startDate, endDate };
}

/**
 * Parse date string to Date object
 */
export function parseDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  try {
    return new Date(dateStr);
  } catch {
    return null;
  }
}

/**
 * Format date for display
 */
export function formatDate(date: Date | string | null): string {
  if (!date) return "N/A";
  const d = typeof date === "string" ? parseDate(date) : date;
  if (!d) return "N/A";
  return d.toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Format date with time
 */
export function formatDateTime(date: Date | string | null): string {
  if (!date) return "N/A";
  const d = typeof date === "string" ? parseDate(date) : date;
  if (!d) return "N/A";
  return d.toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Get month name from date
 */
export function getMonthName(date: Date | string): string {
  const d = typeof date === "string" ? parseDate(date) : date;
  if (!d) return "N/A";
  return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

/**
 * Check if date is today
 */
export function isToday(date: Date | string | null): boolean {
  if (!date) return false;
  const d = typeof date === "string" ? parseDate(date) : date;
  if (!d) return false;
  const today = new Date();
  return (
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear()
  );
}

/**
 * Check if date is in last N days
 */
export function isInLastDays(date: Date | string | null, days: number): boolean {
  if (!date) return false;
  const d = typeof date === "string" ? parseDate(date) : date;
  if (!d) return false;
  const now = new Date();
  const diffTime = now.getTime() - d.getTime();
  const diffDays = diffTime / (1000 * 60 * 60 * 24);
  return diffDays >= 0 && diffDays <= days;
}

/**
 * Group bills by date
 */
export function groupBillsByDate(
  bills: Array<{ created_at?: string; bill_date?: string }>
): Record<string, typeof bills> {
  const grouped: Record<string, typeof bills> = {};

  bills.forEach((bill) => {
    const dateStr = bill.bill_date || bill.created_at;
    const date = dateStr ? formatDate(dateStr) : "Unknown";

    if (!grouped[date]) {
      grouped[date] = [];
    }
    grouped[date].push(bill);
  });

  return grouped;
}

/**
 * Group bills by month
 */
export function groupBillsByMonth(
  bills: Array<{ created_at?: string; bill_date?: string }>
): Record<string, typeof bills> {
  const grouped: Record<string, typeof bills> = {};

  bills.forEach((bill) => {
    const dateStr = bill.bill_date || bill.created_at;
    const month = dateStr ? getMonthName(dateStr) : "Unknown";

    if (!grouped[month]) {
      grouped[month] = [];
    }
    grouped[month].push(bill);
  });

  return grouped;
}

/**
 * Calculate statistics for bills
 */
export function calculateStats(
  bills: Array<{ total_amount?: number }>
): {
  total: number;
  count: number;
  average: number;
  max: number;
  min: number;
} {
  if (bills.length === 0) {
    return { total: 0, count: 0, average: 0, max: 0, min: 0 };
  }

  const amounts = bills
    .map((b) => Number(b.total_amount || 0))
    .filter((a) => a > 0);

  const total = amounts.reduce((a, b) => a + b, 0);
  const count = amounts.length;
  const average = count > 0 ? total / count : 0;
  const max = Math.max(...amounts);
  const min = Math.min(...amounts);

  return { total, count, average, max, min };
}
