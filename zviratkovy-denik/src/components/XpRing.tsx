import React, { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { useAnimatedProps, useSharedValue, withSpring } from 'react-native-reanimated';
import Svg, { Circle, Defs, G, LinearGradient, Stop } from 'react-native-svg';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

const clamp01 = (t: number) => Math.min(1, Math.max(0, t));

/**
 * Soft XP ring. Shows progress toward "the next little change" — it simply
 * refills forever; no numbers, no totals, no finish line.
 */
export function XpRing({
  size,
  stroke = 8,
  progress,
  instant = false,
  trackColor = '#F3E3CB',
  colors = ['#F2A0B8', '#F6C660'],
  children,
}: {
  size: number;
  stroke?: number;
  progress: number;
  /** jump without animating (used mid-celebration when the ring wraps around) */
  instant?: boolean;
  trackColor?: string;
  colors?: [string, string];
  children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  // Keep a tiny sliver visible even at 0 so the ring always feels alive.
  const target = 0.03 + clamp01(progress) * 0.97;
  const p = useSharedValue(target);

  useEffect(() => {
    if (instant) {
      p.value = target;
    } else {
      p.value = withSpring(target, { damping: 22, stiffness: 70, overshootClamping: true });
    }
  }, [target, instant, p]);

  const animatedProps = useAnimatedProps(() => ({
    strokeDashoffset: c * (1 - p.value),
  }));

  return (
    <View style={{ width: size, height: size }}>
      <Svg width={size} height={size}>
        <Defs>
          <LinearGradient id="xpgrad" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor={colors[0]} />
            <Stop offset="1" stopColor={colors[1]} />
          </LinearGradient>
        </Defs>
        <G rotation={-90} origin={`${size / 2}, ${size / 2}`}>
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            stroke={trackColor}
            strokeWidth={stroke}
            fill="none"
          />
          <AnimatedCircle
            cx={size / 2}
            cy={size / 2}
            r={r}
            stroke="url(#xpgrad)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${c} ${c}`}
            animatedProps={animatedProps}
            fill="none"
          />
        </G>
      </Svg>
      {children ? <View style={[StyleSheet.absoluteFill, styles.center]}>{children}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center' },
});
