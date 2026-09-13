import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppImage } from '@/components/AppImage';
import { T } from '@/components/ui';
import type { Category } from '@/config/categories';
import { C, shadowTiny } from '@/config/theme';
import { formatDayBubble, formatTime } from '@/lib/czech';
import { entryCalories, entryPhotos, type Entry } from '@/lib/types';

/** One row in a category's entry list. */
export function EntryCard({
  entry,
  category,
  onPress,
}: {
  entry: Entry;
  category: Category;
  onPress: () => void;
}) {
  const bubble = formatDayBubble(entry.createdAt);
  const photos = entryPhotos(entry);
  const kcal = entryCalories(entry);
  const fieldValues = category.fields
    .filter((f) => f.key !== 'kalorie')
    .map((f) => entry.fields?.[f.key])
    .filter((v): v is string => !!v && v.trim().length > 0);

  const title = entry.note.trim() || fieldValues[0] || 'Bez popisku';

  return (
    <Pressable accessibilityRole="button" onPress={onPress}>
      <View style={styles.card}>
        <View style={[styles.dateBubble, { backgroundColor: category.pale }]}>
          <T v="title" color={category.accentDark} style={{ fontSize: 18, lineHeight: 22 }}>
            {bubble.day}
          </T>
          <T v="tiny" color={category.accentDark} style={{ opacity: 0.8 }}>
            {bubble.month}
          </T>
        </View>

        <View style={styles.middle}>
          <T v="bodyBold" numberOfLines={2}>
            {title}
          </T>
          {fieldValues.length > 0 && entry.note.trim().length > 0 && (
            <T v="small" color={C.inkSoft} numberOfLines={1} style={{ marginTop: 3 }}>
              {fieldValues.join(' · ')}
            </T>
          )}
          <View style={styles.metaRow}>
            <T v="tiny" color={C.inkFaint}>
              {formatTime(entry.createdAt)}
            </T>
            {kcal > 0 && (
              <View style={[styles.kcalChip, { backgroundColor: category.soft }]}>
                <T v="tiny" color={category.accentDark}>
                  {kcal} kcal
                </T>
              </View>
            )}
          </View>
        </View>

        {photos.length > 0 && (
          <View>
            <AppImage uri={photos[0]} style={styles.thumb} contentFit="cover" transition={150} />
            {photos.length > 1 && (
              <View style={styles.moreBadge}>
                <T v="tiny" color={C.white}>
                  +{photos.length - 1}
                </T>
              </View>
            )}
          </View>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: C.card,
    borderRadius: 22,
    padding: 12,
    ...shadowTiny,
  },
  dateBubble: { width: 54, borderRadius: 16, alignItems: 'center', paddingVertical: 8 },
  middle: { flex: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 5 },
  kcalChip: { borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  thumb: { width: 58, height: 58, borderRadius: 16, backgroundColor: C.line },
  moreBadge: {
    position: 'absolute',
    right: -4,
    bottom: -4,
    backgroundColor: C.ink,
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
});
