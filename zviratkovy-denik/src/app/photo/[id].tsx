import { Image } from 'expo-image';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';

import { GhostButton, IconButton, Screen, T } from '@/components/ui';
import { C } from '@/config/theme';
import { formatDateTime } from '@/lib/czech';
import { useApp } from '@/state/AppContext';

export default function PhotoViewScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { entries, deleteEntry } = useApp();

  const entry = entries.find((e) => e.id === id);

  if (!entry?.photoUri) {
    return <Screen bg="#241B13"><View /></Screen>;
  }

  const confirmDelete = () => {
    Alert.alert(
      'Smazat vzpomínku?',
      'Zmizí z deníku, ale všechno nakrmení tvému mazlíčkovi zůstane. 💛',
      [
        { text: 'Nechat', style: 'cancel' },
        {
          text: 'Smazat',
          style: 'destructive',
          onPress: async () => {
            await deleteEntry(entry.id);
            router.back();
          },
        },
      ]
    );
  };

  return (
    <Screen bg="#241B13" edges={['top', 'bottom']}>
      <StatusBar style="light" />
      <View style={styles.headerRow}>
        <View style={{ width: 42 }} />
        <IconButton accessibilityLabel="Zavřít" bg="#FFFFFF22" onPress={() => router.back()}>
          <Text style={{ fontSize: 15, color: '#FFF' }}>✕</Text>
        </IconButton>
      </View>

      <Image source={{ uri: entry.photoUri }} style={styles.photo} contentFit="contain" transition={200} />

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
    paddingHorizontal: 16,
    paddingTop: 10,
  },
  photo: { flex: 1, marginHorizontal: 10, marginTop: 10, borderRadius: 14 },
  captionCard: {
    backgroundColor: '#FFFBF4',
    borderRadius: 24,
    margin: 12,
    padding: 16,
  },
  buttons: { flexDirection: 'row', gap: 12, marginTop: 14 },
});
