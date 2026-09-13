import * as Haptics from 'expo-haptics';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { CategoryCard } from '@/components/CategoryCard';
import { GreeceScene, SceneSparkle } from '@/components/GreeceScene';
import { T } from '@/components/ui';
import { CATEGORIES } from '@/config/categories';
import { PERSONAL } from '@/config/personal';
import { C, shadowTiny } from '@/config/theme';
import { greetingForHour, plural } from '@/lib/czech';
import { useApp } from '@/state/AppContext';

const SPARKLE_SETS = [
  ['☀️', '🐚', '💙'],
  ['✨', '🌊', '⛵️'],
  ['🩵', '☀️', '🫒'],
];

export default function HomeScreen() {
  const router = useRouter();
  const { entries } = useApp();
  const { width } = useWindowDimensions();
  const [tapTick, setTapTick] = useState(0);

  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const e of entries) map[e.categoryId] = (map[e.categoryId] ?? 0) + 1;
    return map;
  }, [entries]);

  /** 1-based day of the holiday, derived from the very first entry. */
  const dayOfTrip = useMemo(() => {
    if (entries.length === 0) return null;
    const first = entries[entries.length - 1].createdAt;
    const startOfDay = (ms: number) => {
      const d = new Date(ms);
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };
    return Math.floor((startOfDay(Date.now()) - startOfDay(first)) / 86400000) + 1;
  }, [entries]);

  const tapScene = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    setTapTick((t) => t + 1);
  };

  const greeting = greetingForHour(new Date().getHours());
  const sparkles = SPARKLE_SETS[tapTick % SPARKLE_SETS.length];

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <LinearGradient colors={[C.sky, C.bg]} style={StyleSheet.absoluteFill} end={{ x: 0.5, y: 0.5 }} />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
        <SafeAreaView edges={['top']}>
          <View style={styles.header}>
            <T v="display" style={{ fontSize: 26 }}>
              {greeting}, {PERSONAL.herNameVocative}! ☀️
            </T>
            <T v="small" color={C.inkSoft} style={{ marginTop: 2 }}>
              {PERSONAL.subtitle}
            </T>
          </View>

          <Pressable accessibilityRole="button" accessibilityLabel="Řecká scéna" onPress={tapScene}>
            <View style={styles.sceneWrap}>
              <GreeceScene width={Math.min(width - 36, 520)} happyTick={tapTick} />
              {tapTick > 0 && (
                <React.Fragment key={tapTick}>
                  <SceneSparkle emoji={sparkles[0]} dx={-60} delay={0} drift={-14} />
                  <SceneSparkle emoji={sparkles[1]} dx={-8} delay={110} drift={10} />
                  <SceneSparkle emoji={sparkles[2]} dx={44} delay={60} drift={18} />
                </React.Fragment>
              )}
            </View>
          </Pressable>

          {entries.length > 0 && (
            <View style={styles.chipRow}>
              {dayOfTrip !== null && (
                <View style={[styles.chip, shadowTiny]}>
                  <T v="small" color={C.seaInk}>
                    {dayOfTrip}. den v Řecku 🇬🇷
                  </T>
                </View>
              )}
              <View style={[styles.chip, shadowTiny]}>
                <T v="small" color={C.seaInk}>
                  {entries.length} {plural(entries.length, ['vzpomínka', 'vzpomínky', 'vzpomínek'])} 💙
                </T>
              </View>
            </View>
          )}
        </SafeAreaView>

        <View style={styles.grid}>
          {CATEGORIES.map((c, i) => (
            <CategoryCard
              key={c.id}
              category={c}
              count={counts[c.id] ?? 0}
              index={i}
              onPress={() => router.push({ pathname: '/category/[id]', params: { id: c.id } })}
            />
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 20, paddingTop: 10, marginBottom: 4 },
  sceneWrap: { alignItems: 'center', marginTop: 6 },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    justifyContent: 'center',
    marginTop: 10,
    paddingHorizontal: 20,
  },
  chip: {
    backgroundColor: C.card,
    borderRadius: 999,
    paddingVertical: 7,
    paddingHorizontal: 14,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    rowGap: 14,
    paddingHorizontal: 18,
    marginTop: 18,
  },
});
