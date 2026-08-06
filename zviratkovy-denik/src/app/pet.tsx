import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { PetAvatar } from '@/components/PetAvatar';
import { XpRing } from '@/components/XpRing';
import { BackButton, Card, GhostButton, IconButton, Screen, T } from '@/components/ui';
import { C, F } from '@/config/theme';
import { plural } from '@/lib/czech';
import { cosmeticsForLevel, formForLevel, levelFromXp } from '@/lib/xp';
import { useApp } from '@/state/AppContext';

export default function PetScreen() {
  const router = useRouter();
  const { pet, entries, renamePet } = useApp();
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(pet.name);

  const info = useMemo(() => levelFromXp(pet.xp), [pet.xp]);
  const cosmetics = useMemo(() => cosmeticsForLevel(info.level), [info.level]);
  const form = useMemo(() => formForLevel(info.level), [info.level]);

  const lastEntryAt = entries[0]?.createdAt;
  const daysSince = lastEntryAt ? (Date.now() - lastEntryAt) / 86400000 : Infinity;
  const statusLine =
    daysSince < 1
      ? `${pet.name} vrní štěstím 💛`
      : daysSince < 3
        ? `${pet.name} se má báječně a těší se na další zápisek 🌱`
        : `${pet.name} tiše kouká z okna a čeká na tvoje slova ✨`;

  const recentUnlocks = cosmetics.slice(-3).reverse();

  const saveName = () => {
    renamePet(nameDraft);
    setEditingName(false);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
  };

  return (
    <Screen bg="#FFF3E4" edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <BackButton onPress={() => router.back()} />
          <T v="title">Můj mazlíček</T>
          <View style={{ width: 42 }} />
        </View>

        <View style={styles.hero}>
          <XpRing size={252} stroke={11} progress={info.progress}>
            <PetAvatar level={info.level} cosmetics={cosmetics} size={168} animate />
          </XpRing>
          <T v="tiny" center color={C.inkSoft} style={{ marginTop: 10 }}>
            Kousíček po kousíčku k dalšímu překvapení ✨
          </T>
        </View>

        {editingName ? (
          <View style={styles.nameRow}>
            <TextInput
              value={nameDraft}
              onChangeText={setNameDraft}
              autoFocus
              maxLength={20}
              style={styles.nameInput}
              returnKeyType="done"
              onSubmitEditing={saveName}
            />
            <IconButton accessibilityLabel="Uložit jméno" onPress={saveName} size={40} bg={C.sage}>
              <Text style={{ fontSize: 16 }}>✓</Text>
            </IconButton>
            <IconButton
              accessibilityLabel="Zrušit"
              onPress={() => {
                setNameDraft(pet.name);
                setEditingName(false);
              }}
              size={40}>
              <Text style={{ fontSize: 14 }}>✕</Text>
            </IconButton>
          </View>
        ) : (
          <View style={styles.nameRow}>
            <T v="display" style={{ fontSize: 30 }}>
              {pet.name}
            </T>
            <IconButton
              accessibilityLabel="Přejmenovat mazlíčka"
              onPress={() => {
                setNameDraft(pet.name);
                setEditingName(true);
              }}
              size={38}>
              <Text style={{ fontSize: 14 }}>✏️</Text>
            </IconButton>
          </View>
        )}

        <Card style={styles.card}>
          <T v="body">{statusLine}</T>
          <T v="small" color={C.inkSoft} style={{ marginTop: 6 }}>
            Právě teď je z něj {form} ✨
          </T>
        </Card>

        <Card style={styles.card}>
          <T v="heading" style={{ marginBottom: 10 }}>
            Co má nového
          </T>
          {recentUnlocks.length === 0 ? (
            <T v="body" color={C.inkSoft}>
              Zatím roste a rozkoukává se 🌱 první parádička přijde už brzy!
            </T>
          ) : (
            recentUnlocks.map((u) => (
              <View key={u.key} style={styles.unlockRow}>
                <Text style={{ fontSize: 18 }}>{u.emoji}</Text>
                <T v="body">{u.label}</T>
              </View>
            ))
          )}
          <View style={styles.unlockRow}>
            <Text style={{ fontSize: 18 }}>🌟</Text>
            <T v="body" color={C.inkSoft}>
              …a další překvapení jsou na cestě
            </T>
          </View>
        </Card>

        <Card style={styles.card}>
          <T v="body">
            Deníček zatím schoval{' '}
            <T v="bodyBold">
              {entries.length} {plural(entries.length, ['zápisek', 'zápisky', 'zápisků'])}
            </T>{' '}
            — a každý z nich se počítá 💛
          </T>
        </Card>

        <View style={{ marginTop: 18, paddingHorizontal: 20 }}>
          <GhostButton label="Vzkaz pro tebe ♡" color={C.pinkDark} onPress={() => router.push('/love-note')} />
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingBottom: 44, paddingTop: 8 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    marginBottom: 6,
  },
  hero: { alignItems: 'center', marginTop: 10 },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginTop: 10,
  },
  nameInput: {
    backgroundColor: C.card,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: C.line,
    paddingVertical: 8,
    paddingHorizontal: 16,
    fontFamily: F.bodyBold,
    fontSize: 18,
    color: C.ink,
    minWidth: 170,
    textAlign: 'center',
  },
  card: { marginHorizontal: 20, marginTop: 14 },
  unlockRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
});
