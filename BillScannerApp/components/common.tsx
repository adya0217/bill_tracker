/**
 * Common UI components for Bill Tracker
 */

import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { COLORS } from "@/constants/api";

// Loading spinner with text
export function LoadingSpinner({
  message = "Loading...",
  color = COLORS.primary,
}: {
  message?: string;
  color?: string;
}) {
  return (
    <View style={styles.centerContainer}>
      <ActivityIndicator size="large" color={color} />
      <Text style={[styles.loadingText, { color }]}>{message}</Text>
    </View>
  );
}

// Error message display
export function ErrorMessage({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <View style={styles.errorContainer}>
      <Text style={styles.errorTitle}>❌ Error</Text>
      <Text style={styles.errorMessage}>{message}</Text>
      {onRetry && (
        <TouchableOpacity style={styles.retryButton} onPress={onRetry}>
          <Text style={styles.retryButtonText}>Try Again</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

// Empty state
export function EmptyState({
  icon = "📭",
  title,
  message,
  action,
  actionText,
}: {
  icon?: string;
  title: string;
  message: string;
  action?: () => void;
  actionText?: string;
}) {
  return (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyIcon}>{icon}</Text>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyMessage}>{message}</Text>
      {action && actionText && (
        <TouchableOpacity style={styles.emptyButton} onPress={action}>
          <Text style={styles.emptyButtonText}>{actionText}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

// Card component
export function Card({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: any;
}) {
  return <View style={[styles.card, style]}>{children}</View>;
}

// Card title
export function CardTitle({ children }: { children: string }) {
  return <Text style={styles.cardTitle}>{children}</Text>;
}

// Card description
export function CardDescription({ children }: { children: string }) {
  return <Text style={styles.cardDescription}>{children}</Text>;
}

// Primary button
export function Button({
  onPress,
  label,
  disabled = false,
  loading = false,
  style,
}: {
  onPress: () => void;
  label: string;
  disabled?: boolean;
  loading?: boolean;
  style?: any;
}) {
  return (
    <TouchableOpacity
      style={[styles.button, disabled && styles.buttonDisabled, style]}
      onPress={onPress}
      disabled={disabled || loading}
    >
      {loading ? (
        <ActivityIndicator size="small" color={COLORS.white} />
      ) : (
        <Text style={styles.buttonText}>{label}</Text>
      )}
    </TouchableOpacity>
  );
}

// Secondary button
export function SecondaryButton({
  onPress,
  label,
  disabled = false,
  loading = false,
  style,
}: {
  onPress: () => void;
  label: string;
  disabled?: boolean;
  loading?: boolean;
  style?: any;
}) {
  return (
    <TouchableOpacity
      style={[styles.secondaryButton, disabled && styles.secondaryButtonDisabled, style]}
      onPress={onPress}
      disabled={disabled || loading}
    >
      {loading ? (
        <ActivityIndicator size="small" color={COLORS.dark} />
      ) : (
        <Text style={styles.secondaryButtonText}>{label}</Text>
      )}
    </TouchableOpacity>
  );
}

// Stat box (for showing key metrics)
export function StatBox({
  label,
  value,
  color = COLORS.primary,
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <View style={styles.statBox}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
    </View>
  );
}

// Progress bar
export function ProgressBar({
  value,
  max,
  color = COLORS.primary,
  label,
}: {
  value: number;
  max: number;
  color?: string;
  label?: string;
}) {
  const percent = max > 0 ? (value / max) * 100 : 0;

  return (
    <View style={styles.progressContainer}>
      {label && <Text style={styles.progressLabel}>{label}</Text>}
      <View style={styles.progressBar}>
        <View
          style={[
            styles.progressFill,
            { width: `${percent}%`, backgroundColor: color },
          ]}
        />
      </View>
      <Text style={styles.progressValue}>{value.toFixed(0)}</Text>
    </View>
  );
}

// List item
export function ListItem({
  title,
  subtitle,
  rightText,
  onPress,
  disabled = false,
}: {
  title: string;
  subtitle?: string;
  rightText?: string;
  onPress?: () => void;
  disabled?: boolean;
}) {
  return (
    <TouchableOpacity
      style={[styles.listItem, disabled && styles.listItemDisabled]}
      onPress={onPress}
      disabled={disabled}
    >
      <View style={{ flex: 1 }}>
        <Text style={styles.listItemTitle}>{title}</Text>
        {subtitle && <Text style={styles.listItemSubtitle}>{subtitle}</Text>}
      </View>
      {rightText && <Text style={styles.listItemRight}>{rightText}</Text>}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    gap: 12,
  },
  loadingText: {
    fontSize: 14,
    fontWeight: "600",
  },
  errorContainer: {
    backgroundColor: "#fee2e2",
    borderWidth: 1,
    borderColor: "#fecaca",
    borderRadius: 8,
    padding: 12,
    marginVertical: 8,
  },
  errorTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#b91c1c",
    marginBottom: 4,
  },
  errorMessage: {
    fontSize: 12,
    color: "#b91c1c",
    marginBottom: 8,
  },
  retryButton: {
    backgroundColor: "#b91c1c",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    alignSelf: "flex-start",
  },
  retryButtonText: {
    color: COLORS.white,
    fontSize: 12,
    fontWeight: "600",
  },
  emptyContainer: {
    alignItems: "center",
    paddingVertical: 32,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: COLORS.dark,
    marginBottom: 4,
  },
  emptyMessage: {
    fontSize: 13,
    color: COLORS.gray,
    textAlign: "center",
    marginBottom: 16,
  },
  emptyButton: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
  },
  emptyButtonText: {
    color: COLORS.white,
    fontSize: 13,
    fontWeight: "600",
  },
  card: {
    backgroundColor: COLORS.white,
    borderRadius: 12,
    padding: 14,
    marginBottom: 14,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: COLORS.dark,
    marginBottom: 4,
  },
  cardDescription: {
    fontSize: 12,
    color: COLORS.gray,
    marginBottom: 10,
  },
  button: {
    backgroundColor: COLORS.primary,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 6,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: COLORS.white,
    fontWeight: "600",
    fontSize: 14,
  },
  secondaryButton: {
    backgroundColor: COLORS.lightGray,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 6,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryButtonDisabled: {
    opacity: 0.6,
  },
  secondaryButtonText: {
    color: COLORS.dark,
    fontWeight: "600",
    fontSize: 14,
  },
  statBox: {
    flex: 1,
    marginRight: 6,
  },
  statLabel: {
    fontSize: 11,
    color: COLORS.gray,
    marginBottom: 2,
  },
  statValue: {
    fontSize: 15,
    fontWeight: "600",
  },
  progressContainer: {
    marginVertical: 8,
    gap: 4,
  },
  progressLabel: {
    fontSize: 12,
    color: COLORS.dark,
    fontWeight: "500",
  },
  progressBar: {
    height: 8,
    backgroundColor: COLORS.lightGray,
    borderRadius: 4,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 4,
  },
  progressValue: {
    fontSize: 11,
    color: COLORS.gray,
    textAlign: "right",
  },
  listItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.lightGray,
  },
  listItemDisabled: {
    opacity: 0.5,
  },
  listItemTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.dark,
    marginBottom: 2,
  },
  listItemSubtitle: {
    fontSize: 12,
    color: COLORS.gray,
  },
  listItemRight: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.dark,
  },
});
