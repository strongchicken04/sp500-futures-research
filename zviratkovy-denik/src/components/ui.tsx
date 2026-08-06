import * as Haptics from 'expo-haptics';
import React from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type PressableProps,
  type StyleProp,
  type TextProps,
  type TextStyle,
  type ViewProps,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView, type Edges } from 'react-native-safe-area-context';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';

import { C, F, R, shadowTiny } from '@/config/theme';

/* ------------------------------------------------------------------ */
/* Typography                                                          */
/* ------------------------------------------------------------------ */

const textVariants = StyleSheet.create({
  display: { fontFamily: F.display, fontSize: 26, lineHeight: 34, color: C.ink },
  title: { fontFamily: F.title, fontSize: 21, lineHeight: 28, color: C.ink },
  heading: { fontFamily: F.semi, fontSize: 17, lineHeight: 23, color: C.ink },
  body: { fontFamily: F.body, fontSize: 15, lineHeight: 22, color: C.ink },
  bodyBold: { fontFamily: F.bodyBold, fontSize: 15, lineHeight: 22, color: C.ink },
  small: { fontFamily: F.bodyMed, fontSize: 13, lineHeight: 18, color: C.ink },
  tiny: { fontFamily: F.bodyMed, fontSize: 11.5, lineHeight: 16, color: C.inkSoft },
});

export type TextVariant = keyof typeof textVariants;

export function T({
  v = 'body',
  color,
  center,
  style,
  children,
  ...rest
}: TextProps & { v?: TextVariant; color?: string; center?: boolean }) {
  return (
    <Text
      {...rest}
      style={[textVariants[v], color ? { color } : null, center ? { textAlign: 'center' } : null, style]}>
      {children}
    </Text>
  );
}

/* ------------------------------------------------------------------ */
/* Layout                                                              */
/* ------------------------------------------------------------------ */

export function Screen({
  children,
  bg = C.bg,
  edges = ['top', 'bottom'],
  style,
}: {
  children: React.ReactNode;
  bg?: string;
  edges?: Edges;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <SafeAreaView edges={edges} style={[{ flex: 1, backgroundColor: bg }, style]}>
      {children}
    </SafeAreaView>
  );
}

export function Card({ style, children, ...rest }: ViewProps) {
  return (
    <View {...rest} style={[styles.card, style]}>
      {children}
    </View>
  );
}

/* ------------------------------------------------------------------ */
/* Buttons                                                             */
/* ------------------------------------------------------------------ */

function usePressScale() {
  const scale = useSharedValue(1);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const onPressIn = () => {
    scale.value = withSpring(0.96, { damping: 20, stiffness: 300 });
  };
  const onPressOut = () => {
    scale.value = withSpring(1, { damping: 16, stiffness: 220 });
  };
  return { animatedStyle, onPressIn, onPressOut };
}

export function PrimaryButton({
  label,
  onPress,
  disabled,
  color = C.pinkDeep,
  textColor = C.white,
  style,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  color?: string;
  textColor?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const { animatedStyle, onPressIn, onPressOut } = usePressScale();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled}
      onPressIn={onPressIn}
      onPressOut={onPressOut}
      onPress={() => {
        Haptics.selectionAsync().catch(() => {});
        onPress();
      }}>
      <Animated.View
        style={[
          styles.primaryButton,
          { backgroundColor: disabled ? C.line : color },
          !disabled && shadowTiny,
          animatedStyle,
          style,
        ]}>
        <T v="bodyBold" color={disabled ? C.inkFaint : textColor} style={{ fontSize: 16 }}>
          {label}
        </T>
      </Animated.View>
    </Pressable>
  );
}

export function GhostButton({
  label,
  onPress,
  color = C.ink,
  borderColor = C.line,
  style,
}: {
  label: string;
  onPress: () => void;
  color?: string;
  borderColor?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const { animatedStyle, onPressIn, onPressOut } = usePressScale();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPressIn={onPressIn}
      onPressOut={onPressOut}
      onPress={() => {
        Haptics.selectionAsync().catch(() => {});
        onPress();
      }}>
      <Animated.View style={[styles.ghostButton, { borderColor }, animatedStyle, style]}>
        <T v="bodyBold" color={color}>
          {label}
        </T>
      </Animated.View>
    </Pressable>
  );
}

export function IconButton({
  children,
  onPress,
  size = 42,
  bg = C.card,
  accessibilityLabel,
  style,
}: {
  children: React.ReactNode;
  onPress: () => void;
  size?: number;
  bg?: string;
  accessibilityLabel: string;
  style?: StyleProp<ViewStyle>;
}) {
  const { animatedStyle, onPressIn, onPressOut } = usePressScale();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      hitSlop={8}
      onPressIn={onPressIn}
      onPressOut={onPressOut}
      onPress={() => {
        Haptics.selectionAsync().catch(() => {});
        onPress();
      }}>
      <Animated.View
        style={[
          styles.iconButton,
          { width: size, height: size, borderRadius: size / 2, backgroundColor: bg },
          shadowTiny,
          animatedStyle,
          style,
        ]}>
        {children}
      </Animated.View>
    </Pressable>
  );
}

export function BackButton({ onPress, color = C.ink }: { onPress: () => void; color?: string }) {
  return (
    <IconButton onPress={onPress} accessibilityLabel="Zpět">
      <Text style={{ fontFamily: F.title, fontSize: 24, color, marginTop: -3 }}>‹</Text>
    </IconButton>
  );
}

export function Chip({
  label,
  selected,
  onPress,
  accent = C.pinkDeep,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  accent?: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={() => {
        Haptics.selectionAsync().catch(() => {});
        onPress();
      }}
      style={[
        styles.chip,
        { borderColor: selected ? accent : C.line, backgroundColor: selected ? accent : C.card },
      ]}>
      <T v="small" color={selected ? C.white : C.inkSoft} style={{ fontFamily: F.bodyBold }}>
        {label}
      </T>
    </Pressable>
  );
}

/* ------------------------------------------------------------------ */
/* Empty state                                                         */
/* ------------------------------------------------------------------ */

export function EmptyState({ emoji, title, text }: { emoji: string; title: string; text: string }) {
  return (
    <View style={styles.empty}>
      <Text style={{ fontSize: 52, marginBottom: 10 }}>{emoji}</Text>
      <T v="heading" center>
        {title}
      </T>
      <T v="body" center color={C.inkSoft} style={{ marginTop: 6, maxWidth: 260 }}>
        {text}
      </T>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: C.card,
    borderRadius: R.l,
    padding: 16,
    ...shadowTiny,
  },
  primaryButton: {
    borderRadius: 24,
    paddingVertical: 15,
    paddingHorizontal: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ghostButton: {
    borderRadius: 24,
    paddingVertical: 12,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    backgroundColor: C.card,
  },
  iconButton: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  chip: {
    borderRadius: 999,
    borderWidth: 1.5,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  empty: {
    alignItems: 'center',
    paddingVertical: 46,
    paddingHorizontal: 24,
  },
});
