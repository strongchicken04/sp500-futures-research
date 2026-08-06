import * as Haptics from 'expo-haptics';
import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, {
  Easing,
  FadeIn,
  FadeInUp,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from 'react-native-reanimated';

import { PetAvatar } from '@/components/PetAvatar';
import { XpRing } from '@/components/XpRing';
import { PrimaryButton, T } from '@/components/ui';
import type { Activity } from '@/config/activities';
import { C } from '@/config/theme';
import { cosmeticsForLevel, type FeedResult } from '@/lib/xp';

/** Praise lines — phrased so they work for any pet name/gender. */
const PRAISES = [
  'Mňam! {name} si moc pochutnává 💛',
  '{name} spokojeně vrní ✨',
  'Krásný zápisek! {name} má velikou radost 🌱',
  'Tvoje slova chutnají ze všeho nejvíc 💫',
  '{name} se olizuje až za ušima 🍽️',
];

type Phase = 'arrive' | 'fed' | 'done';

export function FeedCelebration({
  activity,
  result,
  petName,
  onDone,
}: {
  activity: Activity;
  result: FeedResult;
  petName: string;
  onDone: () => void;
}) {
  const [phase, setPhase] = useState<Phase>('arrive');
  const [displayLevel, setDisplayLevel] = useState(result.oldLevel);
  const [ringProgress, setRingProgress] = useState(result.oldProgress);
  const [ringInstant, setRingInstant] = useState(false);
  const [happyTick, setHappyTick] = useState(0);
  const [heartsShown, setHeartsShown] = useState(false);
  const [poofShown, setPoofShown] = useState(false);

  const praise = useMemo(() => {
    const line = PRAISES[Math.floor(Math.random() * PRAISES.length)];
    return line.replace('{name}', petName);
  }, [petName]);

  /* --- flying food --- */
  const foodX = useSharedValue(-70);
  const foodY = useSharedValue(180);
  const foodScale = useSharedValue(0.4);
  const foodOpacity = useSharedValue(0);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    const at = (ms: number, fn: () => void) => timers.push(setTimeout(fn, ms));

    at(260, () => {
      foodOpacity.value = withTiming(1, { duration: 140 });
      foodX.value = withTiming(0, { duration: 640, easing: Easing.out(Easing.quad) });
      foodY.value = withTiming(6, { duration: 640, easing: Easing.inOut(Easing.quad) });
      foodScale.value = withTiming(1, { duration: 520 });
    });
    at(890, () => {
      foodScale.value = withTiming(0.15, { duration: 170 });
      foodOpacity.value = withTiming(0, { duration: 170 });
    });
    at(990, () => {
      setPhase('fed');
      setHappyTick((t) => t + 1);
      setHeartsShown(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
      setRingProgress(result.leveledUp ? 1 : result.newProgress);
    });

    if (result.leveledUp) {
      at(1760, () => {
        setPoofShown(true);
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      });
      at(2080, () => {
        setDisplayLevel(result.newLevel);
        setRingInstant(true);
        setRingProgress(0);
      });
      at(2190, () => {
        setRingInstant(false);
        setRingProgress(result.newProgress);
      });
      at(2450, () => setPhase('done'));
    } else {
      at(1950, () => setPhase('done'));
    }
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const foodStyle = useAnimatedStyle(() => ({
    opacity: foodOpacity.value,
    transform: [{ translateX: foodX.value }, { translateY: foodY.value }, { scale: foodScale.value }],
  }));

  const cosmetics = useMemo(() => cosmeticsForLevel(displayLevel), [displayLevel]);

  const unlockedLine =
    result.unlocked.length > 0
      ? `Nová parádička: ${result.unlocked.map((u) => `${u.label} ${u.emoji}`).join(' a ')}`
      : null;

  return (
    <Animated.View entering={FadeIn.duration(220)} style={styles.overlay}>
      <Pressable style={StyleSheet.absoluteFill} onPress={phase === 'done' ? onDone : undefined} />
      <View style={styles.center} pointerEvents="box-none">
        <View style={styles.petZone} pointerEvents="none">
          <XpRing size={236} stroke={10} progress={ringProgress} instant={ringInstant}>
            <PetAvatar
              level={displayLevel}
              cosmetics={cosmetics}
              size={150}
              mood={phase !== 'arrive' ? 'happy' : 'idle'}
              happyTick={happyTick}
              animate
            />
          </XpRing>
          <Animated.Text style={[styles.food, foodStyle]}>{activity.foodEmoji}</Animated.Text>
          {heartsShown && <HeartsBurst />}
          {poofShown && <PoofBurst />}
        </View>

        <View style={styles.texts} pointerEvents="none">
          <T v="tiny" center color={C.inkSoft} style={{ letterSpacing: 1.2 }}>
            ZÁPISEK ULOŽEN
          </T>
          {phase !== 'arrive' &&
            (result.leveledUp && poofShown ? (
              <Animated.View entering={FadeInUp.duration(360)}>
                <T v="title" center style={{ marginTop: 6 }}>
                  ✨ Něco se změnilo! ✨
                </T>
                <T v="body" center color={C.inkSoft} style={{ marginTop: 4 }}>
                  {result.formChanged
                    ? `${petName} je teď ${result.newFormLabel}!`
                    : 'Roste a mění se ti před očima 🌱'}
                </T>
                {unlockedLine && (
                  <T v="body" center color={C.pinkDark} style={{ marginTop: 4 }}>
                    {unlockedLine}
                  </T>
                )}
              </Animated.View>
            ) : (
              <Animated.View entering={FadeInUp.duration(360)}>
                <T v="title" center style={{ marginTop: 6 }}>
                  {praise}
                </T>
              </Animated.View>
            ))}
        </View>

        {phase === 'done' && (
          <Animated.View entering={FadeInUp.duration(300)} style={{ marginTop: 22, minWidth: 210 }}>
            <PrimaryButton label="Pokračovat 💛" onPress={onDone} />
          </Animated.View>
        )}
      </View>
    </Animated.View>
  );
}

/* ------------------------------------------------------------------ */
/* Little bursts                                                       */
/* ------------------------------------------------------------------ */

function RisingHeart({ emoji, dx, delay, drift }: { emoji: string; dx: number; delay: number; drift: number }) {
  const t = useSharedValue(0);
  useEffect(() => {
    t.value = withDelay(delay, withTiming(1, { duration: 1150, easing: Easing.out(Easing.quad) }));
  }, [delay, t]);
  const style = useAnimatedStyle(() => ({
    opacity: interpolate(t.value, [0, 0.12, 0.72, 1], [0, 1, 1, 0]),
    transform: [
      { translateY: interpolate(t.value, [0, 1], [8, -110]) },
      { translateX: interpolate(t.value, [0, 1], [0, drift]) },
      { scale: interpolate(t.value, [0, 0.2, 1], [0.5, 1, 0.9]) },
    ],
  }));
  return (
    <Animated.Text style={[styles.heart, { marginLeft: dx }, style]} pointerEvents="none">
      {emoji}
    </Animated.Text>
  );
}

function HeartsBurst() {
  return (
    <>
      <RisingHeart emoji="💛" dx={-70} delay={0} drift={-18} />
      <RisingHeart emoji="✨" dx={-28} delay={130} drift={12} />
      <RisingHeart emoji="🩷" dx={6} delay={60} drift={-8} />
      <RisingHeart emoji="⭐️" dx={40} delay={210} drift={16} />
      <RisingHeart emoji="💫" dx={72} delay={310} drift={26} />
    </>
  );
}

function PoofParticle({ angle, dist, emoji, delay }: { angle: number; dist: number; emoji: string; delay: number }) {
  const t = useSharedValue(0);
  useEffect(() => {
    t.value = withDelay(delay, withTiming(1, { duration: 680, easing: Easing.out(Easing.cubic) }));
  }, [delay, t]);
  const style = useAnimatedStyle(() => ({
    opacity: interpolate(t.value, [0, 0.15, 0.8, 1], [0, 1, 0.9, 0]),
    transform: [
      { translateX: Math.cos(angle) * dist * t.value },
      { translateY: Math.sin(angle) * dist * t.value },
      { scale: interpolate(t.value, [0, 0.3, 1], [0.5, 1.15, 0.9]) },
    ],
  }));
  return (
    <Animated.Text style={[styles.poofParticle, style]} pointerEvents="none">
      {emoji}
    </Animated.Text>
  );
}

function PoofBurst() {
  const flash = useSharedValue(0);
  useEffect(() => {
    flash.value = withTiming(1, { duration: 560, easing: Easing.out(Easing.quad) });
  }, [flash]);
  const flashStyle = useAnimatedStyle(() => ({
    opacity: interpolate(flash.value, [0, 0.25, 1], [0, 0.85, 0]),
    transform: [{ scale: interpolate(flash.value, [0, 1], [0.3, 2.5]) }],
  }));
  const emojis = ['✨', '⭐️', '💛', '✨', '🌟', '💫', '✨', '⭐️'];
  return (
    <>
      <Animated.View style={[styles.flash, flashStyle]} pointerEvents="none" />
      {emojis.map((e, i) => (
        <PoofParticle
          key={i}
          emoji={e}
          angle={(i / emojis.length) * Math.PI * 2 - Math.PI / 2}
          dist={96 + (i % 3) * 14}
          delay={i * 26}
        />
      ))}
    </>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(255,247,236,0.985)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 50,
  },
  center: { alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24 },
  petZone: { alignItems: 'center', justifyContent: 'center' },
  food: { position: 'absolute', fontSize: 42 },
  heart: { position: 'absolute', top: '46%', fontSize: 24 },
  poofParticle: { position: 'absolute', fontSize: 26 },
  flash: {
    position: 'absolute',
    width: 130,
    height: 130,
    borderRadius: 65,
    backgroundColor: '#FFF3D6',
  },
  texts: { marginTop: 18, minHeight: 92, justifyContent: 'flex-start' },
});
