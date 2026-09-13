import React, { useEffect } from 'react';
import Animated, {
  Easing,
  useAnimatedProps,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Circle, Defs, Ellipse, G, LinearGradient, Path, Rect, Stop } from 'react-native-svg';

const AnimatedG = Animated.createAnimatedComponent(G);

const VB_W = 320;
const VB_H = 180;
export const SCENE_ASPECT = VB_H / VB_W;

/** A whitewashed cliff house with a blue dome. */
function House({ x, y, s = 1 }: { x: number; y: number; s?: number }) {
  const w = 34 * s;
  const h = 26 * s;
  return (
    <G>
      <Rect x={x} y={y} width={w} height={h} rx={3 * s} fill="#FFFFFF" />
      <Rect x={x} y={y + h - 3 * s} width={w} height={3 * s} rx={1.5 * s} fill="#EAF2F7" />
      {/* dome */}
      <Path
        d={`M ${x + w * 0.18} ${y} a ${w * 0.32} ${w * 0.3} 0 0 1 ${w * 0.64} 0 Z`}
        fill="#2E8BC0"
      />
      <Path d={`M ${x + w / 2} ${y - w * 0.3} v ${-4 * s}`} stroke="#2E8BC0" strokeWidth={1.6 * s} />
      {/* windows */}
      <Rect x={x + 6 * s} y={y + 9 * s} width={6 * s} height={8 * s} rx={2 * s} fill="#2E8BC0" opacity={0.75} />
      <Rect x={x + 20 * s} y={y + 9 * s} width={6 * s} height={8 * s} rx={2 * s} fill="#2E8BC0" opacity={0.75} />
    </G>
  );
}

/** Cozy Santorini scene: sun, sea, whitewashed houses, a little boat. */
export function GreeceScene({ width, happyTick = 0 }: { width: number; happyTick?: number }) {
  const height = width * SCENE_ASPECT;

  const sun = useSharedValue(0);
  const wave = useSharedValue(0);
  const boat = useSharedValue(0);
  const bounce = useSharedValue(0);

  useEffect(() => {
    sun.value = withRepeat(withTiming(1, { duration: 2600, easing: Easing.inOut(Easing.sin) }), -1, true);
    wave.value = withRepeat(withTiming(1, { duration: 2100, easing: Easing.inOut(Easing.sin) }), -1, true);
    boat.value = withRepeat(withTiming(1, { duration: 9000, easing: Easing.inOut(Easing.quad) }), -1, true);
  }, [sun, wave, boat]);

  const prev = React.useRef(happyTick);
  useEffect(() => {
    if (happyTick === prev.current) return;
    prev.current = happyTick;
    bounce.value = withSequence(
      withTiming(1, { duration: 140 }),
      withSpring(0, { damping: 8, stiffness: 160 })
    );
  }, [happyTick, bounce]);

  const sunProps = useAnimatedProps(() => ({ opacity: 0.75 + sun.value * 0.25 }));
  const waveProps = useAnimatedProps(() => ({ transform: [{ translateX: -8 + wave.value * 16 }] }));
  const boatProps = useAnimatedProps(() => ({
    transform: [{ translateX: boat.value * 42 }, { translateY: wave.value * 2 }],
  }));
  const sceneStyle = useAnimatedStyle(() => ({ transform: [{ scale: 1 + bounce.value * 0.03 }] }));

  return (
    <Animated.View style={[{ width, height }, sceneStyle]}>
      <Svg width={width} height={height} viewBox={`0 0 ${VB_W} ${VB_H}`}>
        <Defs>
          <LinearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#DCF0FA" />
            <Stop offset="1" stopColor="#F6FBFE" />
          </LinearGradient>
          <LinearGradient id="seaGrad" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#7FC6E6" />
            <Stop offset="1" stopColor="#2E8BC0" />
          </LinearGradient>
        </Defs>

        <Rect x={0} y={0} width={VB_W} height={VB_H} fill="url(#sky)" />

        {/* sun */}
        <AnimatedG animatedProps={sunProps}>
          <Circle cx={252} cy={44} r={30} fill="#FBE3A0" opacity={0.45} />
          <Circle cx={252} cy={44} r={19} fill="#F6C445" />
        </AnimatedG>

        {/* birds */}
        <Path d="M 60 34 q 5 -5 10 0 q 5 -5 10 0" stroke="#8FB4C9" strokeWidth={2} fill="none" strokeLinecap="round" />
        <Path d="M 92 22 q 4 -4 8 0 q 4 -4 8 0" stroke="#8FB4C9" strokeWidth={1.7} fill="none" strokeLinecap="round" />

        {/* sea */}
        <Path d={`M 0 116 L ${VB_W} 116 L ${VB_W} ${VB_H} L 0 ${VB_H} Z`} fill="url(#seaGrad)" />
        <AnimatedG animatedProps={waveProps}>
          <Path
            d="M -20 130 q 20 -7 40 0 t 40 0 t 40 0 t 40 0 t 40 0 t 40 0 t 40 0 t 40 0"
            stroke="#FFFFFF"
            strokeWidth={2.5}
            fill="none"
            opacity={0.55}
            strokeLinecap="round"
          />
          <Path
            d="M -20 150 q 20 -7 40 0 t 40 0 t 40 0 t 40 0 t 40 0 t 40 0 t 40 0 t 40 0"
            stroke="#FFFFFF"
            strokeWidth={2}
            fill="none"
            opacity={0.35}
            strokeLinecap="round"
          />
        </AnimatedG>

        {/* little boat */}
        <AnimatedG animatedProps={boatProps}>
          <Path d="M 150 126 l 26 0 l -5 8 l -16 0 Z" fill="#FFFFFF" />
          <Path d="M 163 126 l 0 -16 l 12 16 Z" fill="#E07A5F" />
        </AnimatedG>

        {/* cliff with houses */}
        <Path d={`M 0 116 L 0 60 q 30 -12 58 6 q 24 14 34 50 Z`} fill="#F0E6D8" />
        <Ellipse cx={26} cy={116} rx={54} ry={8} fill="#E6DBCB" />
        <House x={8} y={62} s={1} />
        <House x={46} y={78} s={0.85} />

        {/* tiny olive islet */}
        <G>
          <Ellipse cx={298} cy={116} rx={26} ry={7} fill="#F0E6D8" />
          <Path d="M 298 114 l 0 -14" stroke="#8A6A4A" strokeWidth={3} strokeLinecap="round" />
          <Circle cx={298} cy={94} r={11} fill="#8FA97B" />
          <Circle cx={290} cy={99} r={7} fill="#9FB98B" />
          <Circle cx={306} cy={98} r={7} fill="#7E9A6C" />
        </G>
      </Svg>
    </Animated.View>
  );
}

/** Emoji that floats up when she taps the scene. */
export function useSceneTap() {
  const [tick, setTick] = React.useState(0);
  return { tick, tap: () => setTick((t) => t + 1) };
}

export function SceneSparkle({ emoji, dx, delay, drift }: { emoji: string; dx: number; delay: number; drift: number }) {
  const t = useSharedValue(0);
  useEffect(() => {
    t.value = withDelay(delay, withTiming(1, { duration: 950, easing: Easing.out(Easing.quad) }));
  }, [delay, t]);
  const style = useAnimatedStyle(() => ({
    opacity: t.value < 0.12 ? t.value / 0.12 : t.value > 0.7 ? (1 - t.value) / 0.3 : 1,
    transform: [{ translateY: -70 * t.value }, { translateX: drift * t.value }, { scale: 0.6 + t.value * 0.5 }],
  }));
  return (
    <Animated.Text
      style={[{ position: 'absolute', top: 30, left: '50%', marginLeft: dx, fontSize: 22, zIndex: 5 }, style]}
      pointerEvents="none">
      {emoji}
    </Animated.Text>
  );
}
