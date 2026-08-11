import { useLocalSearchParams, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import React, { useState } from 'react';
import { FlatList, StyleSheet, Text, View, useWindowDimensions } from 'react-native';

import { AppImage } from '@/components/AppImage';
import { GhostButton, IconButton, Screen, T } from '@/components/ui';
import { confirmAction } from '@/lib/confirm';
import { C } from '@/config/theme';
import { formatDateTime } from '@/lib/czech';
import { entryPhotos } from '@/lib/types';
import { useApp } from '@/state/AppContext';

export default function PhotoViewScreen() {
  const router = useRouter();
  const { id, index } = useLocalSearchParams<{ id: string; index?: string }>();
  const { entries, deleteEntry } = useApp();
  const { width } = useWindowDimensions();

  const entry = entries.find((e) => e.id === id);
  const photos = entry ? entryPhotos(entry) : [];
  const start = Math.min(Math.max(0, Number(index) || 0), Math.max(0, photos.length - 1));
  const [page, setPage] = useState(start);
  const [listHeight, setListHeight] = useState(0);

  if (!entry || photos.length === 0) {
    return (
      <Screen bg="#241B13">
        <View />
      </Screen>
    );
  }

  const confirmDelete = () => {
    confirmAction(
      'Smazat vzpomínku?',
      'Zmizí z deníku, ale všechno nakrmení tvému mazlíčkovi zůstane. 💛',
      'Smazat',
      async () => {
        await deleteEntry(entry.id);
        router.back();
      }
    );
  };

  return (
    <Screen bg="#241B13" edges={['top', 'bottom']}>
      <StatusBar style="light" />
      <View style={styles.headerRow}>
        {photos.length > 1 ? (
          <View style={styles.counter}>
            <T v="small" color="#FFF">
              {page + 1} / {photos.length}
            </T>
          </View>
        ) : (
          <View style={{ width: 42 }} />
        )}
        <IconButton accessibilityLabel="Zavřít" bg="#FFFFFF22" onPress={() => router.back()}>
          <Text style={{ fontSize: 15, color: '#FFF' }}>✕</Text>
        </IconButton>
      </View>

      <View style={{ flex: 1 }} onLayout={(e) => setListHeight(e.nativeEvent.layout.height)}>
        {listHeight > 0 && (
          <FlatList
            data={photos}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            keyExtractor={(u, i) => `${u}-${i}`}
            initialScrollIndex={start}
            getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
            onMomentumScrollEnd={(e) =>
              setPage(
                Math.min(photos.length - 1, Math.round(e.nativeEvent.contentOffset.x / width))
              )
            }
            renderItem={({ item }) => (
              <View style={{ width, height: listHeight, padding: 10 }}>
                <AppImage uri={item} style={styles.photo} contentFit="contain" transition={200} />
              </View>
            )}
          />
        )}
      </View>

      {photos.length > 1 && (
        <View style={styles.dots}>
          {photos.map((_, i) => (
            <View key={i} style={[styles.dot, i === page && styles.dotActive]} />
          ))}
        </View>
      )}

      <View style={styles.captionCard}>
        <T v="body" style={{ fontSize: 16, lineHeight: 23 }}>
          {entry.note}
        </T>
        <T v="tiny" color={C.inkSoft} style={{ marginTop: 6 }}>
          🕰 {formatDateTime(entry.createdAt)}
        </T>
        <View style={styles.buttons}>
          <View style={{ flex: 1 }}>
            <GhostButton
              label="Upravit ✏️"
              onPress={() => router.push({ pathname: '/entry/form', params: { entryId: entry.id } })}
            />
          </View>
          <View style={{ flex: 1 }}>
            <GhostButton label="Smazat" color={C.danger} borderColor="#F0D4CB" onPress={confirmDelete} />
          </View>
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 10,
  },
  counter: {
    backgroundColor: '#FFFFFF22',
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  photo: { flex: 1, borderRadius: 14 },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 6, paddingTop: 6 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#FFFFFF44' },
  dotActive: { backgroundColor: '#FFFFFFDD' },
  captionCard: {
    backgroundColor: '#FFFBF4',
    borderRadius: 24,
    margin: 12,
    padding: 16,
  },
  buttons: { flexDirection: 'row', gap: 12, marginTop: 14 },
});
