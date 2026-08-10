import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import React, { useMemo } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import { AppImage } from '@/components/AppImage';
import { EntryCard } from '@/components/EntryCard';
import { BackButton, EmptyState, PrimaryButton, Screen, T } from '@/components/ui';
import { getActivity } from '@/config/activities';
import { C, shadowTiny } from '@/config/theme';
import { formatDateLong } from '@/lib/czech';
import type { Entry } from '@/lib/types';
import { useApp } from '@/state/AppContext';

export default function IslandScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { entries } = useApp();

  const activity = getActivity(id);
  const list = useMemo(
    () => entries.filter((e) => e.activityId === activity?.id),
    [entries, activity?.id]
  );

  if (!activity) return <Redirect href="/" />;

  const openForm = () =>
    router.push({ pathname: '/entry/form', params: { activityId: activity.id } });

  const header = (
    <View>
      <View style={styles.headerRow}>
        <BackButton onPress={() => router.back()} />
        <View style={{ alignItems: 'center' }}>
          <T v="title" color={activity.accentDark}>
            {activity.emoji} {activity.name}
          </T>
          <T v="tiny" color={activity.accentDark} style={{ opacity: 0.7 }}>
            {activity.tagline}
          </T>
        </View>
        <View style={{ width: 42 }} />
      </View>
      <View style={{ paddingHorizontal: 18, marginTop: 12, marginBottom: 16 }}>
        <PrimaryButton label={activity.addLabel} color={activity.accent} onPress={openForm} />
      </View>
    </View>
  );

  const empty = (
    <EmptyState emoji={activity.emoji} title={activity.emptyTitle} text={activity.emptyText} />
  );

  if (activity.id === 'fotky') {
    return (
      <Screen bg={activity.pale} edges={['top']}>
        <FlatList
          data={list}
          key="photo-grid"
          numColumns={2}
          keyExtractor={(e) => e.id}
          ListHeaderComponent={header}
          ListEmptyComponent={empty}
          columnWrapperStyle={{ gap: 12, paddingHorizontal: 18 }}
          contentContainerStyle={{ paddingBottom: 40, gap: 12 }}
          showsVerticalScrollIndicator={false}
          renderItem={({ item }) => <PhotoTile entry={item} onPress={() => router.push({ pathname: '/photo/[id]', params: { id: item.id } })} />}
        />
      </Screen>
    );
  }

  return (
    <Screen bg={activity.pale} edges={['top']}>
      <FlatList
        data={list}
        key="entry-list"
        keyExtractor={(e) => e.id}
        ListHeaderComponent={header}
        ListEmptyComponent={empty}
        contentContainerStyle={{ paddingBottom: 40, paddingHorizontal: 18, gap: 12 }}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => (
          <EntryCard
            entry={item}
            activity={activity}
            onPress={() => router.push({ pathname: '/entry/[id]', params: { id: item.id } })}
          />
        )}
      />
    </Screen>
  );
}

function PhotoTile({ entry, onPress }: { entry: Entry; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.tileSlot}>
      <View style={styles.tile}>
        <AppImage uri={entry.photoUri} style={styles.tileImage} contentFit="cover" transition={180} />
        <View style={{ padding: 10 }}>
          <T v="small" numberOfLines={2}>
            {entry.note}
          </T>
          <T v="tiny" color={C.inkFaint} style={{ marginTop: 3 }}>
            {formatDateLong(entry.createdAt)}
          </T>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    paddingTop: 8,
  },
  tileSlot: { flex: 1 },
  tile: {
    backgroundColor: C.card,
    borderRadius: 20,
    overflow: 'hidden',
    ...shadowTiny,
  },
  tileImage: { width: '100%', aspectRatio: 1, backgroundColor: C.line },
});
