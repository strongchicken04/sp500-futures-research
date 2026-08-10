import { useLocalSearchParams, useRouter } from 'expo-router';
import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { AppImage } from '@/components/AppImage';
import { BackButton, Card, GhostButton, IconButton, Screen, T } from '@/components/ui';
import { confirmAction } from '@/lib/confirm';
import { getActivity } from '@/config/activities';
import { C } from '@/config/theme';
import { formatDateTime } from '@/lib/czech';
import { useApp } from '@/state/AppContext';

export default function EntryDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { entries, deleteEntry } = useApp();

  const entry = entries.find((e) => e.id === id);
  const activity = getActivity(entry?.activityId);

  // Can be briefly empty right after deletion — render nothing while navigating back.
  if (!entry || !activity) return <Screen bg={C.bg}><View /></Screen>;

  const confirmDelete = () => {
    confirmAction(
      'Smazat zápisek?',
      'Zmizí z deníku, ale všechno nakrmení tvému mazlíčkovi zůstane. 💛',
      'Smazat',
      async () => {
        await deleteEntry(entry.id);
        router.back();
      }
    );
  };

  const fieldRows = activity.fields
    .map((f) => ({ label: f.label, value: entry.fields?.[f.key] }))
    .filter((r): r is { label: string; value: string } => !!r.value);

  return (
    <Screen bg={activity.pale} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <BackButton onPress={() => router.back()} />
          <T v="title" color={activity.accentDark}>
            {activity.emoji} {activity.name}
          </T>
          <IconButton
            accessibilityLabel="Upravit zápisek"
            onPress={() => router.push({ pathname: '/entry/form', params: { entryId: entry.id } })}>
            <Text style={{ fontSize: 15 }}>✏️</Text>
          </IconButton>
        </View>

        {entry.photoUri && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Zobrazit fotku"
            onPress={() => router.push({ pathname: '/photo/[id]', params: { id: entry.id } })}>
            <AppImage uri={entry.photoUri} style={styles.photo} contentFit="cover" transition={180} />
          </Pressable>
        )}

        <Card style={{ marginTop: 14, paddingVertical: 10 }}>
          <T v="small" color={C.inkSoft}>
            🕰 {formatDateTime(entry.createdAt)}
          </T>
        </Card>

        <Card style={{ marginTop: 12 }}>
          <T v="tiny" color={C.inkSoft} style={{ marginBottom: 6, letterSpacing: 0.8 }}>
            {activity.noteLabel.toUpperCase()}
          </T>
          <T v="body" style={{ fontSize: 16, lineHeight: 24 }}>
            {entry.note}
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
                </T>
              </View>
            ))}
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
  buttons: { flexDirection: 'row', gap: 12, marginTop: 22 },
});
