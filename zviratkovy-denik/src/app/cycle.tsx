import * as Haptics from 'expo-haptics';
import { useRouter } from 'expo-router';
import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { BackButton, Card, Screen, T } from '@/components/ui';
import { C } from '@/config/theme';
import { addDaysISO, computeStats, diffDaysISO, fromISO, toISO } from '@/lib/cycle';
import { formatDateLong } from '@/lib/czech';
import { loadJSON, saveJSON, STORAGE_KEYS } from '@/lib/storage';

const WEEKDAYS = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne'];
const MONTHS = [
  'Leden',
  'Únor',
  'Březen',
  'Duben',
  'Květen',
  'Červen',
  'Červenec',
  'Srpen',
  'Září',
  'Říjen',
  'Listopad',
  'Prosinec',
];

const ROSE = '#E2608A';
const ROSE_PALE = '#FBE7EF';

export default function CycleScreen() {
  const router = useRouter();
  const todayISO = toISO(new Date());
  const [days, setDays] = useState<string[] | null>(null);
  const [viewYear, setViewYear] = useState(new Date().getFullYear());
  const [viewMonth, setViewMonth] = useState(new Date().getMonth());

  useEffect(() => {
    loadJSON<string[]>(STORAGE_KEYS.cycle, []).then((d) => setDays([...d].sort()));
  }, []);

  const stats = useMemo(() => computeStats(days ?? [], todayISO), [days, todayISO]);
  const periodSet = useMemo(() => new Set(days ?? []), [days]);
  const predictedSet = useMemo(() => new Set(stats.predictedDays), [stats.predictedDays]);

  const toggleDay = (iso: string) => {
    if (iso > todayISO) return; // bleeding can't be logged into the future
    Haptics.selectionAsync().catch(() => {});
    setDays((prev) => {
      const s = new Set(prev ?? []);
      if (s.has(iso)) s.delete(iso);
      else s.add(iso);
      const arr = [...s].sort();
      void saveJSON(STORAGE_KEYS.cycle, arr);
      return arr;
    });
  };

  const moveMonth = (delta: number) => {
    const d = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
  };

  /* status lines */
  const statusLines: { text: string; strong?: boolean }[] = [];
  if (!stats.hasData) {
    statusLines.push({
      text: 'Ťukni v kalendáři na dny, kdy jsi měla menstruaci. Jakmile zapíšeš dva začátky, spočítám ti délku cyklu i předpověď. 🌸',
    });
  } else {
    if (stats.dayOfCycle) statusLines.push({ text: `Dnes je ${stats.dayOfCycle}. den cyklu`, strong: true });
    statusLines.push({
      text: stats.avgCycleKnown
        ? `Průměrný cyklus: ${stats.avgCycleDays} dní · menstruace ~${stats.avgPeriodDays} dní`
        : `Zatím počítám s cyklem ${stats.avgCycleDays} dní — upřesní se po další menstruaci ✨`,
    });
    if (stats.predictionStale) {
      statusLines.push({ text: 'Předpověď se zase chytne, až zapíšeš první den další menstruace ✨' });
    } else if (stats.predictedStart) {
      const inDays = diffDaysISO(todayISO, stats.predictedStart);
      statusLines.push({
        text:
          inDays > 1
            ? `Další menstruace kolem ${formatDateLong(fromISO(stats.predictedStart).getTime())} (za ${inDays} dní)`
            : inDays === 1
              ? 'Další menstruace nejspíš zítra 🌸'
              : inDays === 0
                ? 'Další menstruace nejspíš dnes 🌸'
                : 'Menstruace může přijít každým dnem 🌸',
        strong: true,
      });
    }
  }

  return (
    <Screen bg="#FDF0F5" edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <BackButton onPress={() => router.back()} />
          <T v="title" color={ROSE}>
            Můj cyklus 🌸
          </T>
          <View style={{ width: 42 }} />
        </View>

        <Card style={styles.card}>
          {statusLines.map((l, i) => (
            <T key={i} v={l.strong ? 'bodyBold' : 'body'} color={l.strong ? ROSE : C.ink} style={{ marginTop: i === 0 ? 0 : 6 }}>
              {l.text}
            </T>
          ))}
        </Card>

        <Card style={styles.card}>
          {/* month navigation */}
          <View style={styles.monthRow}>
            <Pressable accessibilityRole="button" accessibilityLabel="Předchozí měsíc" hitSlop={10} onPress={() => moveMonth(-1)}>
              <T v="title" color={ROSE}>
                ‹
              </T>
            </Pressable>
            <T v="heading">
              {MONTHS[viewMonth]} {viewYear}
            </T>
            <Pressable accessibilityRole="button" accessibilityLabel="Další měsíc" hitSlop={10} onPress={() => moveMonth(1)}>
              <T v="title" color={ROSE}>
                ›
              </T>
            </Pressable>
          </View>

          <View style={styles.weekHeader}>
            {WEEKDAYS.map((w) => (
              <View key={w} style={styles.cell}>
                <T v="tiny" color={C.inkSoft}>
                  {w}
                </T>
              </View>
            ))}
          </View>

          <MonthGrid
            year={viewYear}
            month={viewMonth}
            todayISO={todayISO}
            periodSet={periodSet}
            predictedSet={predictedSet}
            onToggle={toggleDay}
          />

          <View style={styles.legend}>
            <View style={[styles.legendDot, { backgroundColor: ROSE }]} />
            <T v="tiny" color={C.inkSoft}>
              menstruace
            </T>
            <View style={[styles.legendDot, styles.legendPredicted]} />
            <T v="tiny" color={C.inkSoft}>
              předpověď
            </T>
            <View style={[styles.legendDot, styles.legendToday]} />
            <T v="tiny" color={C.inkSoft}>
              dnes
            </T>
          </View>
        </Card>

        <T v="tiny" center color={C.inkSoft} style={{ marginTop: 12, paddingHorizontal: 30 }}>
          Ťukni na den a přidáš ho nebo ubereš. Všechno zůstává jen v tomhle telefonu. 💛
        </T>
      </ScrollView>
    </Screen>
  );
}

function MonthGrid({
  year,
  month,
  todayISO,
  periodSet,
  predictedSet,
  onToggle,
}: {
  year: number;
  month: number;
  todayISO: string;
  periodSet: Set<string>;
  predictedSet: Set<string>;
  onToggle: (iso: string) => void;
}) {
  const first = new Date(year, month, 1);
  const lead = (first.getDay() + 6) % 7; // Monday-first
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array.from({ length: lead }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <View style={styles.grid}>
      {cells.map((d, i) => {
        if (d === null) return <View key={`x${i}`} style={styles.cell} />;
        const iso = toISO(new Date(year, month, d));
        const isPeriod = periodSet.has(iso);
        const isPredicted = !isPeriod && predictedSet.has(iso);
        const isToday = iso === todayISO;
        return (
          <Pressable
            key={iso}
            accessibilityRole="button"
            accessibilityLabel={`Den ${d}`}
            onPress={() => onToggle(iso)}
            style={styles.cell}>
            <View
              style={[
                styles.dayCircle,
                isPredicted && styles.dayPredicted,
                isPeriod && styles.dayPeriod,
                isToday && styles.dayToday,
              ]}>
              <T v="small" color={isPeriod ? C.white : iso > todayISO ? C.inkFaint : C.ink}>
                {d}
              </T>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingBottom: 40, paddingTop: 8 },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    marginBottom: 8,
  },
  card: { marginHorizontal: 18, marginTop: 12 },
  monthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 10,
    marginBottom: 8,
  },
  weekHeader: { flexDirection: 'row' },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: {
    width: `${100 / 7}%`,
    aspectRatio: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dayCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dayPeriod: { backgroundColor: ROSE },
  dayPredicted: {
    backgroundColor: ROSE_PALE,
    borderWidth: 1.5,
    borderColor: ROSE,
    borderStyle: 'dashed',
  },
  dayToday: { borderWidth: 2, borderColor: C.gold },
  legend: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 10,
  },
  legendDot: { width: 14, height: 14, borderRadius: 7 },
  legendPredicted: {
    backgroundColor: ROSE_PALE,
    borderWidth: 1.5,
    borderColor: ROSE,
    borderStyle: 'dashed',
    marginLeft: 10,
  },
  legendToday: { borderWidth: 2, borderColor: C.gold, marginLeft: 10 },
});
