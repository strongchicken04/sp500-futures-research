import { LinearGradient } from 'expo-linear-gradient';
import { Redirect, useRouter } from 'expo-router';
import React, { useMemo } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { IslandCard } from '@/components/IslandCard';
import { PetAvatar } from '@/components/PetAvatar';
import { XpRing } from '@/components/XpRing';
import { IconButton, T } from '@/components/ui';
import { ACTIVITIES } from '@/config/activities';
import { PERSONAL } from '@/config/personal';
import { C, shadowTiny } from '@/config/theme';
import { greetingForHour, pickForToday } from '@/lib/czech';
import { cosmeticsForLevel, levelFromXp } from '@/lib/xp';
import { useApp } from '@/state/AppContext';

/** Pet-centric lines — the pet is always the subject, so any name works. */
const PET_MOOD_LINES = [
  '{name} se dnes culí od ucha k uchu',
  '{name} se těší na tvůj dnešní zápisek',
  '{name} dnes vypadá moc spokojeně',
  '{name} si tiše brouká a čeká na tebe',
  '{name} má dnes chlupatou náladu 🌱',
];

export default function HomeScreen() {
  const router = useRouter();
  const { settings, pet, entries } = useApp();

  const levelInfo = useMemo(() => levelFromXp(pet.xp), [pet.xp]);
  const cosmetics = useMemo(() => cosmeticsForLevel(levelInfo.level), [levelInfo.level]);
  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const e of entries) map[e.activityId] = (map[e.activityId] ?? 0) + 1;
    return map;
  }, [entries]);
  const moodLine = useMemo(
    () => pickForToday(PET_MOOD_LINES).replace('{name}', pet.name),
    [pet.name]
  );

  if (!settings.onboarded) return <Redirect href="/onboarding" />;

  const greeting = greetingForHour(new Date().getHours());

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <LinearGradient
        colors={['#FFEFD4', C.bg]}
        style={StyleSheet.absoluteFill}
        end={{ x: 0.5, y: 0.55 }}
      />
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 42 }}>
        <SafeAreaView edges={['top']}>
          {/* header */}
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <T v="display" style={{ fontSize: 25 }}>
                {greeting}, {PERSONAL.herNameVocative}! 💛
              </T>
            </View>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <IconButton accessibilityLabel="Můj mazlíček" onPress={() => router.push('/pet')}>
                <Text style={{ fontSize: 19 }}>🐾</Text>
              </IconButton>
              <IconButton accessibilityLabel="Vzkaz pro tebe" onPress={() => router.push('/love-note')}>
                <Text style={{ fontSize: 19 }}>♡</Text>
              </IconButton>
            </View>
          </View>

          {/* pet hero */}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Otevřít mazlíčka ${pet.name}`}
            onPress={() => router.push('/pet')}
            style={styles.petZone}>
            <PetAvatar level={levelInfo.level} cosmetics={cosmetics} size={205} animate />
            <View style={styles.petMeta}>
              <XpRing size={46} stroke={6} progress={levelInfo.progress}>
                <Text style={{ fontSize: 15 }}>✨</Text>
              </XpRing>
              <View style={[styles.moodBubble, shadowTiny]}>
                <T v="small" color={C.inkSoft}>
                  {moodLine}
                </T>
              </View>
            </View>
          </Pressable>
        </SafeAreaView>

        {/* the sea of islands */}
        <View style={styles.sea}>
          <View style={styles.bubbleA} />
          <View style={styles.bubbleB} />
          <View style={styles.bubbleC} />
          <Text style={styles.seaFish}>🐟</Text>
          <T v="title" color={C.seaInk}>
            Tvoje ostrůvky 🏝️
          </T>
          <T v="small" color={C.seaInk} style={{ opacity: 0.75, marginTop: 2, marginBottom: 14 }}>
            Ťukni na ostrůvek a přidej zápisek ✍️
          </T>
          <View style={styles.grid}>
            {ACTIVITIES.map((a, i) => (
              <IslandCard
                key={a.id}
                activity={a}
                count={counts[a.id] ?? 0}
                index={i}
                onPress={() => router.push({ pathname: '/island/[id]', params: { id: a.id } })}
              />
            ))}
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 10,
    gap: 12,
  },
  petZone: { alignItems: 'center', marginTop: 6 },
  petMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 2,
    paddingHorizontal: 24,
  },
  moodBubble: {
    backgroundColor: C.card,
    borderRadius: 18,
    paddingVertical: 8,
    paddingHorizontal: 14,
    maxWidth: 250,
  },
  sea: {
    marginHorizontal: 14,
    marginTop: 18,
    backgroundColor: C.sea,
    borderRadius: 34,
    padding: 16,
    paddingTop: 20,
    overflow: 'hidden',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    rowGap: 14,
  },
  bubbleA: {
    position: 'absolute',
    top: 18,
    right: -30,
    width: 110,
    height: 110,
    borderRadius: 55,
    backgroundColor: '#FFFFFF2E',
  },
  bubbleB: {
    position: 'absolute',
    bottom: -44,
    left: -30,
    width: 150,
    height: 150,
    borderRadius: 75,
    backgroundColor: '#FFFFFF24',
  },
  bubbleC: {
    position: 'absolute',
    top: 96,
    left: -18,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#FFFFFF22',
  },
  seaFish: {
    position: 'absolute',
    right: 20,
    top: 24,
    fontSize: 16,
    opacity: 0.65,
    transform: [{ scaleX: -1 }],
  },
});
