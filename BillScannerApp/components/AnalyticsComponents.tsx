/**
 * Analytics UI components
 *
 * Fix: removed unused `getCategoryColor` import.
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import {
  CategoryStat,
  StoreStat,
  DayStat,
  MonthStat,
  YearStat,
  AnalyticsSummary,
} from "@/types";
import { COLORS } from "@/constants/api";
import { formatCurrency } from "@/utils/helpers";   // getCategoryColor removed – was unused
import { Card, CardTitle, CardDescription, StatBox } from "./common";

// ─────────────────────────────────────────────
// SUMMARY HEADER
// ─────────────────────────────────────────────

export function SummaryHeader({ summary }: { summary: AnalyticsSummary }) {
  const avgPerBill =
    summary.bill_count > 0 ? summary.total_spend / summary.bill_count : 0;

  return (
    <Card>
      <CardTitle>Overall Summary</CardTitle>
      <CardDescription>High-level view of your bill history on this device.</CardDescription>
      <View style={styles.summaryRow}>
        <StatBox label="Total Spend" value={formatCurrency(summary.total_spend)} />
        <StatBox label="Bills"        value={summary.bill_count} />
        <StatBox label="Avg per Bill" value={formatCurrency(avgPerBill)} />
      </View>
    </Card>
  );
}

// ─────────────────────────────────────────────
// GENERIC BAR CHART
// ─────────────────────────────────────────────

function BarChart({
  title,
  description,
  data,
  getLabel,
  getValue,
  emptyMessage,
}: {
  title:        string;
  description:  string;
  data:         any[];
  getLabel:     (item: any) => string;
  getValue:     (item: any) => number;
  emptyMessage: string;
}) {
  if (data.length === 0) {
    return (
      <Card>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
        <Text style={styles.emptyText}>{emptyMessage}</Text>
      </Card>
    );
  }

  const max = Math.max(...data.map(getValue));

  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      <CardDescription>{description}</CardDescription>

      {data.map((item, index) => {
        const label        = getLabel(item);
        const value        = getValue(item);
        const widthPercent = max > 0 ? Math.max(8, (value / max) * 100) : 0;

        return (
          <View key={label + index} style={styles.barRow}>
            <View style={styles.barLabelContainer}>
              <Text style={styles.barLabel} numberOfLines={1}>{label}</Text>
            </View>
            <View style={styles.barTrack}>
              <View style={[styles.barFill, { width: `${widthPercent}%`, backgroundColor: COLORS.primary }]} />
            </View>
            <Text style={styles.barValue}>{formatCurrency(value)}</Text>
          </View>
        );
      })}
    </Card>
  );
}

// ─────────────────────────────────────────────
// CATEGORY BREAKDOWN
// ─────────────────────────────────────────────

export function CategoryBreakdownChart({ categories }: { categories: CategoryStat[] }) {
  return (
    <BarChart
      title="Spend by Category"
      description="Which categories you spend on the most."
      data={categories}
      getLabel={(c) => c.category}
      getValue={(c) => c.total_spend || 0}
      emptyMessage="No category data yet. Scan a few bills first."
    />
  );
}

// ─────────────────────────────────────────────
// STORE BREAKDOWN
// ─────────────────────────────────────────────

export function StoreBreakdownChart({ stores }: { stores: StoreStat[] | undefined }) {
  return (
    <BarChart
      title="Spend by Store / Area"
      description="Your most frequent or expensive merchants."
      data={stores || []}
      getLabel={(s) => s.store}
      getValue={(s) => s.total_spend || 0}
      emptyMessage="No store data yet. Scan bills with merchant information."
    />
  );
}

// ─────────────────────────────────────────────
// DAY BREAKDOWN
// ─────────────────────────────────────────────

export function DayBreakdownChart({ days }: { days: DayStat[] | undefined }) {
  if (!days || days.length === 0) {
    return (
      <Card>
        <CardTitle>Daily Spend</CardTitle>
        <CardDescription>How much you spent each day.</CardDescription>
        <Text style={styles.emptyText}>No daily data available yet.</Text>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>Daily Spend</CardTitle>
      <CardDescription>How much you spent each day.</CardDescription>
      {days.slice(0, 10).map((day) => (
        <View key={day.date} style={styles.dayRow}>
          <View style={styles.dayInfo}>
            <Text style={styles.dayDate}>{day.date}</Text>
            <Text style={styles.dayCount}>{day.bill_count} bill(s)</Text>
          </View>
          <Text style={styles.dayAmount}>{formatCurrency(day.total_spend)}</Text>
        </View>
      ))}
    </Card>
  );
}

// ─────────────────────────────────────────────
// MONTH BREAKDOWN
// ─────────────────────────────────────────────

export function MonthBreakdownChart({ months }: { months: MonthStat[] | undefined }) {
  return (
    <BarChart
      title="Monthly Spend"
      description="How your spending changes over time."
      data={months || []}
      getLabel={(m) => m.month}
      getValue={(m) => m.total_spend || 0}
      emptyMessage="No monthly data yet. Add some dated bills."
    />
  );
}

// ─────────────────────────────────────────────
// YEAR BREAKDOWN
// ─────────────────────────────────────────────

export function YearBreakdownChart({ years }: { years: YearStat[] | undefined }) {
  return (
    <BarChart
      title="Yearly Spend"
      description="Your spending across years."
      data={years || []}
      getLabel={(y) => y.year}
      getValue={(y) => y.total_spend || 0}
      emptyMessage="No yearly data available."
    />
  );
}

// ─────────────────────────────────────────────
// DATE SPENDING LIST
// ─────────────────────────────────────────────

export function DateSpendingList({
  title,
  data,
  emptyMessage,
}: {
  title:        string;
  data:         { date: string; total: number; count: number }[];
  emptyMessage: string;
}) {
  if (data.length === 0) {
    return (
      <Card>
        <CardTitle>{title}</CardTitle>
        <Text style={styles.emptyText}>{emptyMessage}</Text>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      {data.map((item) => (
        <View key={item.date} style={styles.dateRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.dateLabel}>{item.date}</Text>
            <Text style={styles.billCount}>{item.count} bill(s)</Text>
          </View>
          <Text style={styles.dateAmount}>{formatCurrency(item.total)}</Text>
        </View>
      ))}
    </Card>
  );
}

// ─────────────────────────────────────────────
// STYLES
// ─────────────────────────────────────────────

const styles = StyleSheet.create({
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
    gap: 8,
  },
  barRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
    gap: 8,
  },
  barLabelContainer: {
    width: 80,
  },
  barLabel: {
    fontSize: 11,
    color: COLORS.gray,
    fontWeight: "500",
  },
  barTrack: {
    flex: 1,
    height: 8,
    backgroundColor: COLORS.lightGray,
    borderRadius: 4,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 4,
  },
  barValue: {
    fontSize: 12,
    fontWeight: "600",
    color: COLORS.dark,
    width: 60,
    textAlign: "right",
  },
  emptyText: {
    marginTop: 8,
    fontSize: 12,
    color: "#9ca3af",
  },
  dayRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.lightGray,
  },
  dayInfo: {
    flex: 1,
  },
  dayDate: {
    fontSize: 13,
    fontWeight: "600",
    color: COLORS.dark,
  },
  dayCount: {
    fontSize: 11,
    color: COLORS.gray,
    marginTop: 2,
  },
  dayAmount: {
    fontSize: 13,
    fontWeight: "600",
    color: COLORS.dark,
  },
  dateRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.lightGray,
  },
  dateLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: COLORS.dark,
  },
  billCount: {
    fontSize: 11,
    color: COLORS.gray,
    marginTop: 2,
  },
  dateAmount: {
    fontSize: 14,
    fontWeight: "700",
    color: COLORS.primary,
  },
});
