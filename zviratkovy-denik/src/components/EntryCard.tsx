import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppImage } from '@/components/AppImage';

import { T } from '@/components/ui';
import type { Activity } from '@/config/activities';
import { C, shadowTiny } from '@/config/theme';
import { formatDayBubble, formatTime } from '@/lib/czech';
import type { Entry } from '@/lib/types';

/** One row in an island's entry list. */
export function EntryCard({
  entry,
  activity,
  onPress,
}: {
  entry: Entry;
  activity: Activity;
  onPress: () => void;
}) {
  const bubble = formatDayBubble(entry.createdAt);
  const fieldValues = entry.fields
    ? activity.fields
        .map((f) => entry.fields?.[f.key])
        .filter((v): v is string => !!v && v.trim().length > 0)
    : [];

  return (
    <Pressable accessibilityRole="button" onPress={onPress}>
      <View style={styles.card}>
        <View style={[styles.dateBubble, { backgroundColor: activity.pale }]}>
          <T v="title" color={activity.accentDark} style={{ fontSize: 18, lineHeight: 22 }}>
            {bubble.day}
          </T>
          <T v="tiny" color={activity.accentDark} style={{ opacity: 0.8 }}>
            {bubble.month}
          </T>
        </View>
        <View style={styles.middle}>
          <T v="bodyBold" numberOfLines={2}>
            {entry.note}
          </T>
          {fieldValues.length > 0 && (
            <T v="small" color={C.inkSoft} numberOfLines={1} style={{ marginTop: 3 }}>
              {fieldValues.join(' · ')}
            </T>
          )}
          <T v="tiny" color={C.inkFaint} style={{ marginTop: 4 }}>
            {formatTime(entry.createdAt)}
          </T>
        </View>
        {entry.photoUri ? (
          <AppImage uri={entry.photoUri} style={styles.thumb} contentFit="cover" transition={150} />
        ) : null}
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
  dateBubble: {
    width: 54,
    borderRadius: 16,
    alignItems: 'center',
    paddingVertical: 8,
  },
  middle: { flex: 1 },
  thumb: { width: 56, height: 56, borderRadius: 16, backgroundColor: C.line },
});
