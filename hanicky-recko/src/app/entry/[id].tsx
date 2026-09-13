import { useLocalSearchParams, useRouter } from 'expo-router';
import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { AppImage } from '@/components/AppImage';
import { BackButton, Card, GhostButton, IconButton, Screen, T } from '@/components/ui';
import { getCategory } from '@/config/categories';
import { C } from '@/config/theme';
import { confirmAction } from '@/lib/confirm';
import { formatDateTime } from '@/lib/czech';
import { entryPhotos } from '@/lib/types';
import { useApp } from '@/state/AppContext';

export default function EntryDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { entries, deleteEntry } = useApp();

  const entry = entries.find((e) => e.id === id);
  const category = getCategory(entry?.categoryId);

  // Briefly empty right after deletion — render nothing while navigating back.
  if (!entry || !category) {
    return (
      <Screen bg={C.bg}>
        <View />
      </Screen>
    );
  }

  const photos = entryPhotos(entry);
  const fieldRows = category.fields
    .map((f) => ({
      label: f.label,
      value: entry.fields?.[f.key] ?? '',
      suffix: f.type === 'number' ? f.suffix : undefined,
    }))
    .filter((r) => r.value.length > 0);

  const confirmDelete = () => {
    confirmAction('Smazat zápisek?', 'Opravdu ho chceš smazat?', 'Smazat', async () => {
      await deleteEntry(entry.id);
      router.back();
    });
  };

  return (
    <Screen bg={category.pale} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <BackButton onPress={() => router.back()} />
          <T v="title" color={category.accentDark}>
            {category.emoji} {category.name}
          </T>
          <IconButton
            accessibilityLabel="Upravit zápisek"
            onPress={() => router.push({ pathname: '/entry/form', params: { entryId: entry.id } })}>
            <Text style={{ fontSize: 15 }}>✏️</Text>
          </IconButton>
        </View>

        {photos.length > 0 && (
          <>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Zobrazit fotku"
              onPress={() =>
                router.push({ pathname: '/photo/[id]', params: { id: entry.id, index: '0' } })
              }>
              <AppImage uri={photos[0]} style={styles.photo} contentFit="cover" transition={180} />
            </Pressable>
            {photos.length > 1 && (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 10 }}>
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  {photos.slice(1).map((u, i) => (
                    <Pressable
                      key={`${u}-${i}`}
                      accessibilityRole="button"
                      accessibilityLabel={`Zobrazit fotku ${i + 2}`}
                      onPress={() =>
                        router.push({
                          pathname: '/photo/[id]',
                          params: { id: entry.id, index: String(i + 1) },
                        })
                      }>
                      <AppImage uri={u} style={styles.thumb} contentFit="cover" transition={150} />
                    </Pressable>
                  ))}
                </View>
              </ScrollView>
            )}
          </>
        )}

        <Card style={{ marginTop: 14, paddingVertical: 10 }}>
          <T v="small" color={C.inkSoft}>
            🕰 {formatDateTime(entry.createdAt)}
          </T>
        </Card>

        {fieldRows.length > 0 && (
          <Card style={{ marginTop: 12 }}>
            {fieldRows.map((r, i) => (
              <View key={r.label} style={{ marginTop: i === 0 ? 0 : 10 }}>
                <T v="tiny" color={C.inkSoft}>
                  {r.label}
                </T>
                <T v="bodyBold" style={{ marginTop: 2 }}>
                  {r.value}
                  {r.suffix ? ` ${r.suffix}` : ''}
                </T>
              </View>
            ))}
          </Card>
        )}

        {entry.note.trim().length > 0 && (
          <Card style={{ marginTop: 12 }}>
            <T v="body" style={{ fontSize: 16, lineHeight: 24 }}>
              {entry.note}
            </T>
          </Card>
        )}

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
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 18, paddingTop: 8, paddingBottom: 44 },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  photo: { width: '100%', height: 270, borderRadius: 24, backgroundColor: C.line },
  thumb: { width: 72, height: 72, borderRadius: 16, backgroundColor: C.line },
  buttons: { flexDirection: 'row', gap: 12, marginTop: 22 },
});
