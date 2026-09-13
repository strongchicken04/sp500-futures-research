import { Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import React, { useMemo } from 'react';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';

import { AppImage } from '@/components/AppImage';
import { EntryCard } from '@/components/EntryCard';
import { BackButton, EmptyState, PrimaryButton, Screen, T } from '@/components/ui';
import { getCategory } from '@/config/categories';
import { C, shadowTiny } from '@/config/theme';
import { formatDateLong } from '@/lib/czech';
import { entryCalories, entryPhotos, type Entry } from '@/lib/types';
import { useApp } from '@/state/AppContext';

export default function CategoryScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { entries } = useApp();

  const category = getCategory(id);
  const list = useMemo(
    () => entries.filter((e) => e.categoryId === category?.id),
    [entries, category?.id]
  );

  /** Calories logged today (food category only). */
  const kcalToday = useMemo(() => {
    if (category?.id !== 'jidlo') return 0;
    const now = new Date();
    const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    return list
      .filter((e) => e.createdAt >= dayStart)
      .reduce((sum, e) => sum + entryCalories(e), 0);
  }, [list, category?.id]);

  if (!category) return <Redirect href="/" />;

  const openForm = () =>
    router.push({ pathname: '/entry/form', params: { categoryId: category.id } });

  const header = (
    <View>
      <View style={styles.headerRow}>
        <BackButton onPress={() => router.back()} />
        <View style={{ alignItems: 'center' }}>
          <T v="title" color={category.accentDark}>
            {category.emoji} {category.name}
          </T>
          <T v="tiny" color={category.accentDark} style={{ opacity: 0.7 }}>
            {category.tagline}
          </T>
        </View>
        <View style={{ width: 42 }} />
      </View>

      {kcalToday > 0 && (
        <View style={[styles.kcalBar, { backgroundColor: category.soft }]}>
          <T v="bodyBold" color={category.accentDark}>
            Dnes {kcalToday} kcal
          </T>
        </View>
      )}

      <View style={{ paddingHorizontal: 18, marginTop: 12, marginBottom: 16 }}>
        <PrimaryButton label={category.addLabel} color={category.accent} onPress={openForm} />
      </View>
    </View>
  );

  const empty = <EmptyState emoji={category.emoji} title={category.emptyTitle} text={category.emptyText} />;

  if (category.id === 'fotky') {
    return (
      <Screen bg={category.pale} edges={['top']}>
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
          renderItem={({ item }) => (
            <PhotoTile
              entry={item}
              onPress={() => router.push({ pathname: '/photo/[id]', params: { id: item.id } })}
            />
          )}
        />
      </Screen>
    );
  }

  return (
    <Screen bg={category.pale} edges={['top']}>
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
            category={category}
            onPress={() => router.push({ pathname: '/entry/[id]', params: { id: item.id } })}
          />
        )}
      />
    </Screen>
  );
}

function PhotoTile({ entry, onPress }: { entry: Entry; onPress: () => void }) {
  const photos = entryPhotos(entry);
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.tileSlot}>
      <View style={styles.tile}>
        <AppImage uri={photos[0]} style={styles.tileImage} contentFit="cover" transition={180} />
        {photos.length > 1 && (
          <View style={styles.tileBadge}>
            <T v="tiny" color={C.white}>
              +{photos.length - 1}
            </T>
          </View>
        )}
        <View style={{ padding: 10 }}>
          {entry.note.trim().length > 0 && (
            <T v="small" numberOfLines={2}>
              {entry.note}
            </T>
          )}
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
  kcalBar: {
    alignSelf: 'center',
    marginTop: 12,
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 18,
  },
  tileSlot: { flex: 1 },
  tile: { backgroundColor: C.card, borderRadius: 20, overflow: 'hidden', ...shadowTiny },
  tileImage: { width: '100%', aspectRatio: 1, backgroundColor: C.line },
  tileBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: '#00000088',
    borderRadius: 10,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
});
