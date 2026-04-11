/**
 * Bill-specific UI components
 */

import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
} from "react-native";
import { StructuredBill, CategoryBreakdown } from "@/types";
import { COLORS } from "@/constants/api";
import { formatCurrency } from "@/utils/helpers";
import { Card, CardTitle, CardDescription, StatBox } from "./common";

// Bill summary card
export function BillSummaryCard({
  bill,
  categoryBreakdown,
}: {
  bill: StructuredBill;
  categoryBreakdown: CategoryBreakdown;
}) {
  const { totalSpend } = categoryBreakdown;
  const totalItems = bill.items?.length ?? 0;

  return (
    <Card>
      <CardTitle>Bill Summary</CardTitle>
      <CardDescription>Quick overview of this bill.</CardDescription>

      {bill.merchant ? (
        <Text style={styles.merchantText}>{bill.merchant}</Text>
      ) : null}

      <View style={styles.summaryRow}>
        <StatBox label="Total Spend" value={formatCurrency(totalSpend || bill.total_amount)} />
        <StatBox label="Items" value={totalItems} />
        <StatBox
          label="Avg / Item"
          value={formatCurrency(
            totalItems ? (totalSpend || bill.total_amount) / totalItems : 0
          )}
        />
      </View>
    </Card>
  );
}

// Bill items table
export function BillItemsTable({ bill }: { bill: StructuredBill }) {
  if (!bill.items || bill.items.length === 0) {
    return (
      <Card>
        <CardTitle>Line Items</CardTitle>
        <CardDescription>All products detected on this bill.</CardDescription>
        <Text style={styles.emptyText}>
          No items detected. Try a clearer image or different angle.
        </Text>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>Line Items</CardTitle>
      <CardDescription>All products detected on this bill.</CardDescription>

      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View>
          <View style={styles.tableHeader}>
            <Text style={[styles.tableHeaderText, { flex: 3 }]}>Item</Text>
            <Text style={[styles.tableHeaderText, { flex: 1 }]}>Qty</Text>
            <Text style={[styles.tableHeaderText, { flex: 1 }]}>Price</Text>
            <Text style={[styles.tableHeaderText, { flex: 1 }]}>Total</Text>
          </View>

          {bill.items.map((item, index) => {
            const qty = Number(item.quantity || 1);
            const unitPrice = Number(item.unit_price || 0);
            const lineTotal = Number(item.total_price || qty * unitPrice);

            return (
              <View
                key={`${item.name}-${index}`}
                style={[
                  styles.tableRow,
                  index % 2 === 0 && styles.tableRowStriped,
                ]}
              >
                <View style={{ flex: 3 }}>
                  <Text style={styles.itemName}>{item.name}</Text>
                  {item.category && (
                    <Text style={styles.itemCategory}>{item.category}</Text>
                  )}
                </View>
                <Text style={[styles.tableCell, { flex: 1 }]}>{qty || "-"}</Text>
                <Text style={[styles.tableCell, { flex: 1 }]}>
                  {unitPrice ? formatCurrency(unitPrice) : "-"}
                </Text>
                <Text style={[styles.tableCell, { flex: 1 }]}>
                  {lineTotal ? formatCurrency(lineTotal) : "-"}
                </Text>
              </View>
            );
          })}
        </View>
      </ScrollView>
    </Card>
  );
}

// Category breakdown
export function CategoryBreakdownCard({
  categoryBreakdown,
}: {
  categoryBreakdown: CategoryBreakdown;
}) {
  const { categoryTotals, maxTotal } = categoryBreakdown;

  if (Object.keys(categoryTotals).length === 0) {
    return (
      <Card>
        <CardTitle>Spend by Category</CardTitle>
        <CardDescription>Where your money went in this bill.</CardDescription>
        <Text style={styles.emptyText}>
          No categories detected yet. Try scanning a clearer bill image.
        </Text>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>Spend by Category</CardTitle>
      <CardDescription>Where your money went in this bill.</CardDescription>

      {Object.entries(categoryTotals).map(([category, value]) => {
        const percent = maxTotal > 0 ? Math.max(10, (value / maxTotal) * 100) : 0;

        return (
          <View key={category} style={styles.categoryRow}>
            <View style={styles.categoryHeaderRow}>
              <Text style={styles.categoryName}>{category}</Text>
              <Text style={styles.categoryAmount}>{formatCurrency(value)}</Text>
            </View>
            <View style={styles.categoryBarBackground}>
              <View
                style={[
                  styles.categoryBarFill,
                  { width: `${percent}%`, backgroundColor: COLORS.primary },
                ]}
              />
            </View>
          </View>
        );
      })}
    </Card>
  );
}

// Bill preview image
export function BillPreviewImage({
  imageUri,
  onRemove,
}: {
  imageUri: string;
  onRemove?: () => void;
}) {
  return (
    <View style={styles.previewWrapper}>
      <Image source={{ uri: imageUri }} style={styles.previewImage} />
      <View style={styles.previewFooter}>
        <Text style={styles.previewHint}>Preview of the bill used for OCR.</Text>
        {onRemove && (
          <TouchableOpacity onPress={onRemove}>
            <Text style={styles.removeText}>Remove</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
  },
  merchantText: {
    marginTop: 4,
    fontSize: 13,
    color: COLORS.darkGray,
    fontWeight: "500",
  },
  emptyText: {
    marginTop: 8,
    fontSize: 12,
    color: "#9ca3af",
  },
  categoryRow: {
    marginTop: 8,
  },
  categoryHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 2,
  },
  categoryName: {
    fontSize: 12,
    color: COLORS.darkGray,
    fontWeight: "500",
  },
  categoryAmount: {
    fontSize: 12,
    color: COLORS.dark,
    fontWeight: "500",
  },
  categoryBarBackground: {
    height: 8,
    borderRadius: 999,
    backgroundColor: COLORS.lightGray,
    overflow: "hidden",
  },
  categoryBarFill: {
    height: "100%",
    borderRadius: 999,
  },
  tableHeader: {
    flexDirection: "row",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderColor: COLORS.lightGray,
    marginTop: 4,
  },
  tableHeaderText: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.gray,
  },
  tableRow: {
    flexDirection: "row",
    paddingVertical: 6,
    alignItems: "flex-start",
    minWidth: 300,
  },
  tableRowStriped: {
    backgroundColor: "#f9fafb",
  },
  tableCell: {
    fontSize: 11,
    color: COLORS.dark,
    textAlign: "right",
  },
  itemName: {
    fontSize: 12,
    fontWeight: "500",
    color: COLORS.dark,
  },
  itemCategory: {
    fontSize: 10,
    color: COLORS.gray,
    marginTop: 2,
  },
  previewWrapper: {
    marginTop: 12,
    borderRadius: 10,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: COLORS.lightGray,
  },
  previewImage: {
    width: "100%",
    height: 220,
    resizeMode: "cover",
  },
  previewFooter: {
    padding: 8,
    backgroundColor: "#f9fafb",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  previewHint: {
    fontSize: 11,
    color: COLORS.gray,
    flex: 1,
  },
  removeText: {
    fontSize: 12,
    color: "#ef4444",
    fontWeight: "600",
  },
});
