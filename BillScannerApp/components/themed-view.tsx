/**
 * components/themed-view.tsx
 *
 * A View that automatically sets its background colour based on
 * the current light / dark colour scheme.
 */

import React from "react";
import { View, ViewProps } from "react-native";
import { useColorScheme } from "@/hooks/use-color-scheme";
import { Colors } from "@/constants/theme";

export function ThemedView({ style, ...rest }: ViewProps) {
  const scheme          = useColorScheme();
  const backgroundColor = Colors[scheme].background;

  return <View style={[{ backgroundColor }, style]} {...rest} />;
}
