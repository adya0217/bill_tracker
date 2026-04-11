import React, { useState } from "react";
import { View, ScrollView, StyleSheet, TouchableOpacity, Text } from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { DEVICE_ID, COLORS } from "@/constants/api";
import { useAnalytics } from "@/hooks/useAnalytics";
import { LoadingSpinner, ErrorMessage } from "@/components/common";
import {
  SummaryHeader,
  CategoryBreakdownChart,
  StoreBreakdownChart,
  DayBreakdownChart,
  MonthBreakdownChart,
  YearBreakdownChart,
  DateSpendingList,
} from "@/components/AnalyticsComponents";

type DateFilter = "today" | "week" | "month" | "year" | "all";

const FILTERS: { key: DateFilter; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
  { key: "year", label: "Year" },
  { key: "all", label: "All" },
];

export default function AnalyticsScreen() {
  const { summary, loading, error, refresh } = useAnalytics(DEVICE_ID);
  const [activeFilter, setActiveFilter] = useState<DateFilter>("month");

  useFocusEffect(
    React.useCallback(() => {
      refresh();
      const id = setInterval(refresh, 30_000);
      return () => clearInterval(id);
    }, [refresh])
  );

  const shouldShowContent = !loading && !error && summary;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Analysis</Text>
          <Text style={styles.subtitle}>
            Clear spending insights by category, store and time period.
          </Text>
        </View>
        <TouchableOpacity onPress={refresh} disabled={loading} style={styles.refreshPill}>
          <Text style={styles.refreshPillText}>{loading ? "..." : "Refresh"}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.filterContainer}>
        {FILTERS.map((filter) => (
          <TouchableOpacity
            key={filter.key}
            onPress={() => setActiveFilter(filter.key)}
            style={[
              styles.filterPill,
              activeFilter === filter.key && styles.filterPillActive,
            ]}
          >
            <Text
              style={[
                styles.filterPillText,
                activeFilter === filter.key && styles.filterPillTextActive,
              ]}
            >
              {filter.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading && <LoadingSpinner message="Loading analysis..." />}
      {error && !loading && <ErrorMessage message={error} onRetry={refresh} />}

      {shouldShowContent && (
        <>
          <SummaryHeader summary={summary} />
          <CategoryBreakdownChart categories={summary.by_category || []} />
          <StoreBreakdownChart stores={summary.by_store || []} />

          {activeFilter === "today" && (
            <DateSpendingList
              title="Today's Spend"
              data={(summary.by_day || []).map((d) => ({
                date: d.date,
                total: d.total_spend,
                count: d.bill_count,
              }))}
              emptyMessage="No transactions found for today."
            />
          )}

          {(activeFilter === "week" || activeFilter === "month" || activeFilter === "all") && (
            <DayBreakdownChart days={summary.by_day || []} />
          )}

          {(activeFilter === "month" || activeFilter === "year" || activeFilter === "all") && (
            <MonthBreakdownChart months={summary.by_month || []} />
          )}

          {(activeFilter === "year" || activeFilter === "all") && (
            <YearBreakdownChart years={summary.by_year || []} />
          )}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.veryLightGray,
  },
  content: {
    padding: 16,
    paddingBottom: 32,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    color: COLORS.dark,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    color: COLORS.gray,
  },
  refreshPill: {
    backgroundColor: COLORS.white,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderWidth: 1,
    borderColor: COLORS.lightGray,
  },
  refreshPillText: {
    color: COLORS.dark,
    fontSize: 12,
    fontWeight: "600",
  },
  filterContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 12,
  },
  filterPill: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: COLORS.lightGray,
    backgroundColor: COLORS.white,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  filterPillActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  filterPillText: {
    color: COLORS.darkGray,
    fontSize: 12,
    fontWeight: "600",
  },
  filterPillTextActive: {
    color: COLORS.white,
  },
});
