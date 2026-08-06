import { useRouter } from 'expo-router';
import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import Animated, { FadeInDown, FadeInUp } from 'react-native-reanimated';

import { PetAvatar } from '@/components/PetAvatar';
import { Card, PrimaryButton, Screen, T } from '@/components/ui';
import { ACTIVITIES } from '@/config/activities';
import { PERSONAL } from '@/config/personal';
import { C, F } from '@/config/theme';
import { useApp } from '@/state/AppContext';

export default function OnboardingScreen() {
  const router = useRouter();
  const { completeOnboarding } = useApp();
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');

  const finish = () => {
    completeOnboarding(name || PERSONAL.defaultPetName);
    router.replace('/');
  };

  return (
    <Screen bg="#FFF3E4">
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          {step === 0 && (
            <Animated.View key="s0" entering={FadeInDown.duration(420)} style={styles.step}>
              <Text style={styles.bigEmoji}>💛</Text>
              <T v="display" center>
                Ahoj, {PERSONAL.herNameVocative}!
              </T>
              <T v="body" center color={C.inkSoft} style={styles.paragraph}>
                Vítej ve svém deníčku. Je to malý útulný svět jen pro tebe — pro tvoje dny,
                radosti, vzpomínky i fotky.
              </T>
              <PrimaryButton label="Ukaž mi víc ✨" onPress={() => setStep(1)} style={styles.btn} />
            </Animated.View>
          )}

          {step === 1 && (
            <Animated.View key="s1" entering={FadeInDown.duration(420)} style={styles.step}>
              <PetAvatar level={0} size={180} animate />
              <T v="display" center style={{ marginTop: 8 }}>
                Někdo tu na tebe čeká…
              </T>
              <T v="body" center color={C.inkSoft} style={styles.paragraph}>
                Tenhle malinký křeček bude tvůj parťák. Každým zápiskem ho nakrmíš — a on poroste a
                bude se pomaličku měnit v něco moc krásného.
              </T>
              <T v="heading" center style={{ marginTop: 14 }}>
                Jak mu budeš říkat?
              </T>
              <TextInput
                value={name}
                onChangeText={setName}
                placeholder={PERSONAL.defaultPetName}
                placeholderTextColor={C.inkFaint}
                maxLength={20}
                style={styles.input}
                returnKeyType="done"
              />
              <PrimaryButton
                label={`To je ono 💛`}
                onPress={() => setStep(2)}
                style={styles.btn}
              />
            </Animated.View>
          )}

          {step === 2 && (
            <Animated.View key="s2" entering={FadeInDown.duration(420)} style={styles.step}>
              <View style={styles.emojiRow}>
                {ACTIVITIES.map((a) => (
                  <Text key={a.id} style={{ fontSize: 24 }}>
                    {a.emoji}
                  </Text>
                ))}
              </View>
              <T v="display" center style={{ fontSize: 24 }}>
                Jak to funguje?
              </T>
              <T v="body" center color={C.inkSoft} style={styles.paragraph}>
                Na každém ostrůvku si zapisuješ jednu činnost — jídlo, zásilky, školu, judo, spánek
                i fotky. Každý zápisek {name.trim() || PERSONAL.defaultPetName} nakrmí a posune o
                kousíček dál. 🌱
              </T>
              <Animated.View entering={FadeInUp.delay(250).duration(500)} style={{ width: '100%' }}>
                <Card style={styles.noteCard}>
                  <Text style={{ fontSize: 22, textAlign: 'center', marginBottom: 6 }}>💌</Text>
                  <T v="heading" center style={{ marginBottom: 8 }}>
                    {PERSONAL.loveNoteTitle}
                  </T>
                  {PERSONAL.loveNote.split('\n\n').map((p, i) => (
                    <T key={i} v="body" center color={C.inkSoft} style={{ marginBottom: 8 }}>
                      {p}
                    </T>
                  ))}
                  <T v="heading" center color={C.pinkDark} style={{ marginTop: 4 }}>
                    {PERSONAL.loveNoteSignature}
                  </T>
                </Card>
              </Animated.View>
              <PrimaryButton label="Jdeme na to! 🐾" onPress={finish} style={styles.btn} />
            </Animated.View>
          )}

          {/* step dots */}
          <View style={styles.dots}>
            {[0, 1, 2].map((i) => (
              <View
                key={i}
                style={[styles.dot, { backgroundColor: i === step ? C.pinkDeep : C.line }]}
              />
            ))}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 24, paddingBottom: 34 },
  step: { alignItems: 'center' },
  bigEmoji: { fontSize: 64, marginBottom: 12 },
  paragraph: { marginTop: 10, maxWidth: 300 },
  btn: { marginTop: 22, minWidth: 220 },
  input: {
    marginTop: 12,
    backgroundColor: C.card,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: C.line,
    paddingVertical: 12,
    paddingHorizontal: 18,
    fontFamily: F.bodyBold,
    fontSize: 17,
    color: C.ink,
    minWidth: 220,
    textAlign: 'center',
  },
  emojiRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  noteCard: { marginTop: 18, backgroundColor: '#FFF6F8' },
  dots: { flexDirection: 'row', gap: 8, justifyContent: 'center', marginTop: 26 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
