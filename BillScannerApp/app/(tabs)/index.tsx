
import React, { useState } from "react";
import {
  View,
  ScrollView,
  StyleSheet,
  Alert,
  TouchableOpacity,
  Text,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import { useFocusEffect } from "@react-navigation/native";

import { API_ROUTES, DEVICE_ID, COLORS } from "@/constants/api";
import { computeCategoryBreakdown, formatCurrency } from "@/utils/helpers";
import { useBills } from "@/hooks/useBills";
import { StructuredBill, BillListItem } from "@/types";

import {
  LoadingSpinner,
  ErrorMessage,
  EmptyState,
  Card,
  CardTitle,
  CardDescription,
  Button,
  SecondaryButton,
  ListItem,
} from "@/components/common";
import {
  BillSummaryCard,
  BillItemsTable,
  CategoryBreakdownCard,
  BillPreviewImage,
} from "@/components/BillComponents";

export default function BillsHome() {
  const [imageUri, setImageUri]     = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [billData, setBillData]     = useState<StructuredBill | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError]           = useState<string | null>(null);

  const {
    bills, loading: loadingBills,
    page, total, pageSize,
    loadBills, getBillDetails,
    nextPage, prevPage, canNextPage, canPrevPage,
  } = useBills(DEVICE_ID);

  // Refresh bill list every time this tab gains focus
  useFocusEffect(
    React.useCallback(() => {
      loadBills(1);
    }, [loadBills])
  );

  // ──────────────────────────────────────────
  // UPLOAD
  // ──────────────────────────────────────────

  const getFileType = (fileName: string) => {
    const ext = fileName.split(".").pop()?.toLowerCase() || "";
    const map: Record<string, string> = {
      jpg: "image/jpeg",
      jpeg: "image/jpeg",
      png: "image/png",
      webp: "image/webp",
      pdf: "application/pdf",
      doc: "application/msword",
      docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      xls: "application/vnd.ms-excel",
      xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      csv: "text/csv",
      txt: "text/plain",
    };
    return map[ext] || "application/octet-stream";
  };

  const uploadBillToBackend = async (file: { uri: string; name: string; type?: string }) => {
    const isImage = file.type?.startsWith("image/");
    setImageUri(isImage ? file.uri : null);
    setSelectedFileName(file.name);
    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("device_id",      DEVICE_ID);
    formData.append("vendor_id",      "1");
    formData.append("payment_method", "card");
    formData.append("amount_paid",    "0");
    formData.append("points_added",   "0");
    formData.append("file", {
      uri: file.uri,
      name: file.name,
      type: file.type || getFileType(file.name),
    } as any);

    try {
      const uploadUrl = API_ROUTES.bills.upload();
      console.log("[upload] POST", uploadUrl);

      const response = await fetch(uploadUrl, {
        method: "POST",
        body:   formData,
      });

      console.log("[upload] status", response.status);

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status} ${response.statusText} — ${text}`);
      }

      let json: any;
      try {
        json = await response.json();
      } catch (parseErr) {
        const text = await response.text();
        throw new Error(`Invalid JSON from server: ${parseErr} — ${text}`);
      }

      console.log("[upload] response keys:", Object.keys(json));

      if (json.error) {
        setError(json.error);
        Alert.alert("Upload Error", json.error);
        return;
      }

      // ── Normalise response
      // Backend exposes both `name` and `product_name` per item.
      // We prefer `name`; fall back to `product_name` for resilience.
      const normalized: StructuredBill = {
        merchant:    json.merchant     || "",
        bill_date:   json.bill_date    || "",
        bill_number: json.bill_number  || null,   // safe – field may be absent
        subtotal:    Number(json.subtotal     || 0),
        tax:         Number(json.tax          || 0),
        total_amount:Number(json.total_amount || 0),
        // Do NOT re-categorise here – use whatever the backend returned
        items: Array.isArray(json.items)
          ? json.items.map((item: any) => ({
              name:        item.name         || item.product_name || "",
              product_name:item.product_name || item.name         || "",
              sku:         item.sku          || "",
              quantity:    Number(item.quantity   || 1),
              unit_price:  Number(item.unit_price || 0),
              total_price: Number(item.total_price|| 0),
              tax:         Number(item.tax        || 0),
              category:    item.category          || "Other",
            }))
          : [],
      };

      console.log(
        `[upload] ✅ ${normalized.items.length} items, total=${normalized.total_amount}`
      );

      setBillData(normalized);
      loadBills(1);
      Alert.alert("Success", "Bill analysed successfully!");
    } catch (err: any) {
      console.error("[upload] ❌", err);
      setError("Upload failed. Please try again.");
      Alert.alert("Error", `Upload failed: ${err?.message || err}`);
    } finally {
      setIsUploading(false);
    }
  };

  // ──────────────────────────────────────────
  // IMAGE PICKERS
  // ──────────────────────────────────────────

  const pickFromGallery = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"] as const,
      quality: 1,
    });
    if (!result.canceled) {
      const asset = result.assets[0];
      uploadBillToBackend({
        uri: asset.uri,
        name: asset.fileName || "bill-image.jpg",
        type: asset.mimeType || "image/jpeg",
      });
    }
  };

  const captureWithCamera = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Alert.alert("Permission Required", "Camera access is needed to scan bills.");
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ["images"] as const,
      quality: 1,
    });
    if (!result.canceled) {
      const asset = result.assets[0];
      uploadBillToBackend({
        uri: asset.uri,
        name: asset.fileName || `captured-${Date.now()}.jpg`,
        type: asset.mimeType || "image/jpeg",
      });
    }
  };

  const pickDocument = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: [
        "image/*",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "text/plain",
      ],
      copyToCacheDirectory: true,
      multiple: false,
    });

    if (result.canceled) return;
    const file = result.assets[0];
    uploadBillToBackend({
      uri: file.uri,
      name: file.name || `upload-${Date.now()}`,
      type: file.mimeType || getFileType(file.name || ""),
    });
  };

  // ──────────────────────────────────────────
  // BILL SELECTION
  // ──────────────────────────────────────────

  const handleSelectBill = async (bill: BillListItem) => {
    console.log("[selectBill] id=", bill.id);
    const details = await getBillDetails(bill.id);
    if (details) {
      // Normalise items here too in case the detail endpoint returns
      // product_name instead of name (or vice-versa)
      const normalized: StructuredBill = {
        ...details,
        items: (details.items || []).map((item: any) => ({
          ...item,
          name:         item.name         || item.product_name || "",
          product_name: item.product_name || item.name         || "",
          category:     item.category     || "Other",
        })),
      };
      setBillData(normalized);
      setImageUri(null);
      setSelectedFileName(null);
      setError(null);
    }
  };

  const handleClear = () => {
    setImageUri(null);
    setSelectedFileName(null);
    setBillData(null);
    setError(null);
  };

  // ──────────────────────────────────────────
  // RENDER
  // ──────────────────────────────────────────

  const categoryBreakdown = computeCategoryBreakdown(billData);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.appTitle}>Bill Scanner</Text>
        <Text style={styles.appSubtitle}>
          Upload receipts and files to get clean, structured analysis.
        </Text>
      </View>

      {/* ── Capture Section */}
      <Card>
        <View style={styles.cardHeaderRow}>
          <View style={{ flex: 1 }}>
            <CardTitle>Upload & Scan</CardTitle>
            <CardDescription>Camera, gallery, PDF, DOC, Excel and CSV files.</CardDescription>
          </View>
          {billData && (
            <TouchableOpacity onPress={handleClear}>
              <Text style={styles.clearText}>Clear</Text>
            </TouchableOpacity>
          )}
        </View>

        <View style={styles.buttonRow}>
          <Button
            onPress={captureWithCamera}
            label="Camera"
            disabled={isUploading}
            loading={isUploading}
            style={{ flex: 1 }}
          />
          <SecondaryButton
            onPress={pickFromGallery}
            label="Gallery"
            disabled={isUploading}
            style={{ flex: 1, marginLeft: 8 }}
          />
        </View>
        <View style={styles.buttonRow}>
          <SecondaryButton
            onPress={pickDocument}
            label="Browse Files"
            disabled={isUploading}
            style={{ flex: 1 }}
          />
        </View>

        {imageUri && <BillPreviewImage imageUri={imageUri} onRemove={handleClear} />}
        {selectedFileName && (
          <View style={styles.fileTag}>
            <Text style={styles.fileTagText}>Selected: {selectedFileName}</Text>
          </View>
        )}
        {error && !isUploading && <ErrorMessage message={error} />}
      </Card>

      {/* ── Bill Details */}
      {billData && !isUploading && (
        <>
          <View style={styles.analysisHeader}>
            <Text style={styles.analysisTitle}>Analysis</Text>
            <Text style={styles.analysisSubtitle}>Parsed bill insights and line-by-line details.</Text>
          </View>
          <BillSummaryCard bill={billData} categoryBreakdown={categoryBreakdown} />
          <CategoryBreakdownCard categoryBreakdown={categoryBreakdown} />
          <BillItemsTable bill={billData} />
        </>
      )}

      {/* ── Bills List */}
      <Card>
        <View style={styles.listHeaderRow}>
          <View style={{ flex: 1 }}>
            <CardTitle>Your Bills</CardTitle>
            <CardDescription>{`${total} total • Tap to view details`}</CardDescription>
          </View>
          <TouchableOpacity
            onPress={() => loadBills(page)}
            disabled={loadingBills}
            style={styles.refreshButton}
          >
            <Text style={styles.refreshButtonText}>{loadingBills ? "⏳" : "🔄"}</Text>
          </TouchableOpacity>
        </View>

        {loadingBills && bills.length === 0 ? (
          <LoadingSpinner />
        ) : bills.length === 0 && !loadingBills ? (
          <EmptyState
            icon="📭"
            title="No bills yet"
            message="Scan your first bill to get started"
          />
        ) : (
          <>
            {bills.map((bill) => (
              <ListItem
                key={bill.id}
                title={bill.merchant || "Unknown Store"}
                subtitle={bill.bill_date || bill.created_at || "No date"}
                rightText={formatCurrency(bill.total_amount || 0)}
                onPress={() => handleSelectBill(bill)}
                disabled={isUploading}
              />
            ))}

            {/* Pagination */}
            <View style={styles.paginationRow}>
              <SecondaryButton
                onPress={prevPage}
                label="← Prev"
                disabled={!canPrevPage || loadingBills}
                style={{ flex: 1 }}
              />
              <Text style={styles.pageInfo}>
                Page {page} / {Math.ceil(total / pageSize) || 1}
              </Text>
              <SecondaryButton
                onPress={nextPage}
                label="Next →"
                disabled={!canNextPage || loadingBills}
                style={{ flex: 1 }}
              />
            </View>
          </>
        )}
      </Card>
    </ScrollView>
  );
}

// ──────────────────────────────────────────────
// STYLES
// ──────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.veryLightGray,
  },
  content: {
    padding: 16,
    paddingBottom: 32,
  },
  header: {
    marginBottom: 16,
  },
  appTitle: {
    fontSize: 24,
    fontWeight: "700",
    color: COLORS.dark,
    marginBottom: 4,
  },
  appSubtitle: {
    fontSize: 13,
    color: COLORS.gray,
  },
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  clearText: {
    fontSize: 12,
    color: "#ef4444",
    fontWeight: "600",
  },
  buttonRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 8,
  },
  fileTag: {
    marginTop: 10,
    borderRadius: 8,
    backgroundColor: "#eef2ff",
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  fileTagText: {
    color: COLORS.dark,
    fontSize: 12,
    fontWeight: "500",
  },
  analysisHeader: {
    marginBottom: 8,
  },
  analysisTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: COLORS.dark,
  },
  analysisSubtitle: {
    fontSize: 12,
    color: COLORS.gray,
    marginTop: 2,
  },
  listHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  refreshButton: {
    padding: 8,
  },
  refreshButtonText: {
    fontSize: 18,
  },
  paginationRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.lightGray,
  },
  pageInfo: {
    flex: 1,
    textAlign: "center",
    fontSize: 12,
    color: COLORS.gray,
    fontWeight: "600",
  },
});
