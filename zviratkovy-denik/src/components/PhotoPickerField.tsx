import * as ImagePicker from 'expo-image-picker';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppImage } from '@/components/AppImage';
import { T } from '@/components/ui';
import { notify } from '@/lib/confirm';
import { C, F } from '@/config/theme';

export const MAX_PHOTOS_PER_ENTRY = 5;

/** Photo attachment grid: pick several from the camera roll, preview, remove. */
export function PhotoPickerField({
  uris,
  onChange,
  accent,
  max = MAX_PHOTOS_PER_ENTRY,
}: {
  uris: string[];
  onChange: (uris: string[]) => void;
  accent: string;
  max?: number;
}) {
  const remaining = max - uris.length;

  const pick = async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        notify(
          'Potřebuju přístup k fotkám',
          'Povol prosím přístup k fotkám v nastavení telefonu, ať si sem můžeš přidávat vzpomínky. 📸'
        );
        return;
      }
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 0.85,
        allowsMultipleSelection: true,
        selectionLimit: remaining,
      });
      if (!result.canceled && result.assets.length > 0) {
        const picked = result.assets.map((a) => a.uri).slice(0, remaining);
        onChange([...uris, ...picked]);
      }
    } catch (e) {
      console.warn('photo pick failed', e);
    }
  };

  return (
    <View style={styles.grid}>
      {uris.map((uri, i) => (
        <View key={`${uri}-${i}`} style={styles.cell}>
          <AppImage uri={uri} style={styles.preview} contentFit="cover" transition={150} />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Odebrat fotku ${i + 1}`}
            onPress={() => onChange(uris.filter((_, j) => j !== i))}
            style={styles.removeBtn}
            hitSlop={8}>
            <Text style={styles.removeText}>✕</Text>
          </Pressable>
        </View>
      ))}
      {remaining > 0 && (
        <Pressable accessibilityRole="button" accessibilityLabel="Přidat fotku" onPress={pick}>
          <View style={[styles.addTile, { borderColor: accent }]}>
            <Text style={{ fontSize: 20 }}>📸</Text>
            <T v="small" color={accent} style={{ fontFamily: F.bodyBold }}>
              {uris.length === 0 ? 'Vybrat' : 'Přidat'}
            </T>
          </View>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  cell: { width: 96, height: 96 },
  preview: { width: 96, height: 96, borderRadius: 18, backgroundColor: C.line },
  removeBtn: {
    position: 'absolute',
    top: -8,
    right: -8,
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: C.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  removeText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  addTile: {
    width: 96,
    height: 96,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    backgroundColor: '#FFFFFF88',
  },
});
