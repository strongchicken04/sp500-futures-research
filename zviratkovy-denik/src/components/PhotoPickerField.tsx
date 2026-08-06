import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import React from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { T } from '@/components/ui';
import { C } from '@/config/theme';

/** Photo attachment field: pick from the camera roll, preview, remove. */
export function PhotoPickerField({
  uri,
  onPick,
  onRemove,
  accent,
}: {
  uri?: string;
  onPick: (uri: string) => void;
  onRemove: () => void;
  accent: string;
}) {
  const pick = async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert(
          'Potřebuju přístup k fotkám',
          'Povol prosím přístup k fotkám v nastavení telefonu, ať si sem můžeš přidávat vzpomínky. 📸'
        );
        return;
      }
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 0.85,
        selectionLimit: 1,
      });
      if (!result.canceled && result.assets[0]) {
        onPick(result.assets[0].uri);
      }
    } catch (e) {
      console.warn('photo pick failed', e);
    }
  };

  if (uri) {
    return (
      <View style={styles.previewWrap}>
        <Pressable accessibilityRole="button" accessibilityLabel="Vyměnit fotku" onPress={pick}>
          <Image source={{ uri }} style={styles.preview} contentFit="cover" transition={150} />
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Odebrat fotku"
          onPress={onRemove}
          style={styles.removeBtn}
          hitSlop={8}>
          <Text style={styles.removeText}>✕</Text>
        </Pressable>
        <T v="tiny" color={C.inkSoft} style={{ marginTop: 6 }}>
          ťukni na fotku pro výměnu
        </T>
      </View>
    );
  }

  return (
    <Pressable accessibilityRole="button" accessibilityLabel="Vybrat fotku" onPress={pick}>
      <View style={[styles.pickButton, { borderColor: accent }]}>
        <Text style={{ fontSize: 22 }}>📸</Text>
        <T v="bodyBold" color={accent}>
          Vybrat fotku
        </T>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pickButton: {
    borderWidth: 2,
    borderStyle: 'dashed',
    borderRadius: 20,
    paddingVertical: 18,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 10,
    backgroundColor: '#FFFFFF88',
  },
  previewWrap: { alignItems: 'flex-start' },
  preview: { width: 110, height: 110, borderRadius: 20, backgroundColor: C.line },
  removeBtn: {
    position: 'absolute',
    top: -8,
    left: 92,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: C.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  removeText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
});
