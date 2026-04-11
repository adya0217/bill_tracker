/**
 * components/themed-text.tsx
 *
 * Text that automatically uses the correct colour for the current
 * light / dark colour scheme.
 *
 * Supported `type` variants:
 *   default | title | subtitle | link | defaultSemiBold
 */

import React from "react";
import { Text, TextProps, StyleSheet } from "react-native";
import { useColorScheme } from "@/hooks/use-color-scheme";
import { Colors } from "@/constants/theme";

type TextType = "default" | "title" | "subtitle" | "link" | "defaultSemiBold";

export interface ThemedTextProps extends TextProps {
  type?: TextType;
}

export function ThemedText({ style, type = "default", ...rest }: ThemedTextProps) {
  const scheme = useColorScheme();
  const color  = Colors[scheme].text;

  return (
    <Text
      style={[
        { color },
        styles[type],
        style,
      ]}
      {...rest}
    />
  );
}

const styles = StyleSheet.create({
  default: {
    fontSize: 14,
    lineHeight: 22,
  },
  defaultSemiBold: {
    fontSize: 14,
    lineHeight: 22,
    fontWeight: "600",
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    lineHeight: 34,
  },
  subtitle: {
    fontSize: 18,
    fontWeight: "600",
  },
  link: {
    fontSize: 14,
    lineHeight: 22,
    color: "#3b82f6",
    textDecorationLine: "underline",
  },
});
