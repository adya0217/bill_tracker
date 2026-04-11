/**
 * hooks/useBills.ts
 *
 * Manages the paginated bills list and single-bill detail fetch.
 *
 * API shapes supported:
 *   GET /bills/device/{device_id}?skip=0&limit=20
 *     → BillListItem[]
 *   OR legacy/paginated object:
 *     → { items: BillListItem[], page, page_size, total }
 *
 *   GET /bills/{bill_id}
 *     → StructuredBill (with items array)
 */

import { useState, useCallback } from "react";
import { API_ROUTES } from "@/constants/api";
import { BillListItem, StructuredBill } from "@/types";

const PAGE_SIZE = 20;

interface UseBillsReturn {
  bills:        BillListItem[];
  loading:      boolean;
  error:        string | null;
  page:         number;
  total:        number;
  pageSize:     number;
  canNextPage:  boolean;
  canPrevPage:  boolean;
  loadBills:    (page: number) => Promise<void>;
  getBillDetails: (billId: number) => Promise<StructuredBill | null>;
  nextPage:     () => void;
  prevPage:     () => void;
}

export function useBills(deviceId: string): UseBillsReturn {
  const [bills,   setBills]   = useState<BillListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const [page,    setPage]    = useState(1);
  const [total,   setTotal]   = useState(0);

  const loadBills = useCallback(async (requestedPage: number) => {
    setLoading(true);
    setError(null);

    const skip = (requestedPage - 1) * PAGE_SIZE;
    const url = API_ROUTES.bills.byDevice(deviceId, skip, PAGE_SIZE);

    console.log("[useBills] GET", url);

    try {
      const res = await fetch(url);

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status} – ${text}`);
      }

      const json = await res.json();

      const rawItems = Array.isArray(json)
        ? json
        : (json.items || json.bills || []);
      const derivedTotal = Array.isArray(json)
        ? rawItems.length
        : Number(json.total ?? rawItems.length);
      console.log(`[useBills] ${derivedTotal} total bills, page=${requestedPage}`);

      // Normalise list items – guard against missing fields
      const items: BillListItem[] = rawItems.map((b: any) => ({
        id:           b.id,
        merchant:     b.merchant     || "",
        area:         b.area         ?? null,
        bill_date:    b.bill_date    ?? null,
        bill_number:  b.bill_number  ?? null,
        total_amount: Number(b.total_amount ?? 0),
        created_at:   b.created_at   ?? null,
      }));

      setBills(items);
      setPage(requestedPage);
      setTotal(derivedTotal);
    } catch (err: any) {
      console.error("[useBills] fetch error:", err);
      setError(err?.message || "Failed to load bills");
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  const getBillDetails = useCallback(
    async (billId: number): Promise<StructuredBill | null> => {
      const url = API_ROUTES.bills.byId(billId);
      console.log("[useBills] GET detail", url);

      try {
        const res = await fetch(url);

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`HTTP ${res.status} – ${text}`);
        }

        const json = await res.json();

        // Normalise items – backend may use product_name or name
        const items = (json.items || []).map((item: any) => ({
          name:         item.name         || item.product_name || "",
          product_name: item.product_name || item.name         || "",
          sku:          item.sku          || "",
          quantity:     Number(item.quantity   ?? 1),
          unit_price:   Number(item.unit_price ?? 0),
          total_price:  Number(item.total_price ?? 0),
          tax:          Number(item.tax         ?? 0),
          category:     item.category           || "Other",
        }));

        const bill: StructuredBill = {
          id:           json.id,
          merchant:     json.merchant     || "",
          area:         json.area         ?? "",
          bill_date:    json.bill_date    || "",
          bill_number:  json.bill_number  ?? null,
          subtotal:     Number(json.subtotal     ?? 0),
          tax:          Number(json.tax ?? json.total_tax ?? 0),
          total_amount: Number(json.total_amount ?? 0),
          items,
        };

        console.log(`[useBills] detail: ${items.length} items, total=${bill.total_amount}`);
        return bill;
      } catch (err: any) {
        console.error("[useBills] getBillDetails error:", err);
        return null;
      }
    },
    []
  );

  const totalPages  = Math.ceil(total / PAGE_SIZE) || 1;
  const canNextPage = page < totalPages && !loading;
  const canPrevPage = page > 1 && !loading;

  const nextPage = useCallback(() => {
    if (canNextPage) loadBills(page + 1);
  }, [canNextPage, page, loadBills]);

  const prevPage = useCallback(() => {
    if (canPrevPage) loadBills(page - 1);
  }, [canPrevPage, page, loadBills]);

  return {
    bills, loading, error,
    page, total, pageSize: PAGE_SIZE,
    canNextPage, canPrevPage,
    loadBills, getBillDetails,
    nextPage, prevPage,
  };
}
