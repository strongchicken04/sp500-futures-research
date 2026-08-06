import { useRouter } from 'expo-router';
import React, { useEffect } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import Animated, {
  Easing,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { Card, PrimaryButton, Screen, T } from '@/components/ui';
import { PERSONAL } from '@/config/personal';
import { C } from '@/config/theme';

function FloatingHeart({ left, delay, emoji }: { left: number; delay: number; emoji: string }) {
  const t = useSharedValue(0);
  useEffect(() => {
    t.value = withDelay(
      delay,
      withRepeat(withTiming(1, { duration: 5200, easing: Easing.inOut(Easing.quad) }), -1, false)
    );
  }, [delay, t]);
  const style = useAnimatedStyle(() => ({
    opacity: interpolate(t.value, [0, 0.12, 0.8, 1], [0, 0.7, 0.4, 0]),
    transform: [
      { translateY: interpolate(t.value, [0, 1], [40, -420]) },
      { translateX: interpolate(t.value, [0, 0.5, 1], [0, 14, -8]) },
      { scale: interpolate(t.value, [0, 0.2, 1], [0.6, 1, 0.9]) },
    ],
  }));
  return (
    <Animated.Text style={[styles.floatingHeart, { left: `${left}%` }, style]} pointerEvents="none">
      {emoji}
    </Animated.Text>
  );
}

export default function LoveNoteScreen() {
  const router = useRouter();
  return (
    <Screen bg="#FFF1F4" edges={['top', 'bottom']}>
      <FloatingHeart left={12} delay={0} emoji="💛" />
      <FloatingHeart left={46} delay={1700} emoji="🩷" />
      <FloatingHeart left={78} delay={3300} emoji="💛" />
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={{ fontSize: 56, textAlign: 'center' }}>💌</Text>
        <T v="display" center style={{ marginTop: 8 }}>
          {PERSONAL.loveNoteTitle}
        </T>
        <Card style={styles.card}>
          {PERSONAL.loveNote.split('\n\n').map((p, i) => (
            <T key={i} v="body" center color={C.ink} style={{ marginBottom: 12, lineHeight: 24 }}>
              {p}
            </T>
          ))}
          <T v="heading" center color={C.pinkDark} style={{ marginTop: 2 }}>
            {PERSONAL.loveNoteSignature}
          </T>
        </Card>
        <View style={{ marginTop: 24, minWidth: 210 }}>
          <PrimaryButton label="Zavřít 💛" onPress={() => router.back()} />
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  card: { marginTop: 18, backgroundColor: '#FFFDF9', padding: 22, alignSelf: 'stretch' },
  floatingHeart: { position: 'absolute', bottom: 0, fontSize: 26, zIndex: 10 },
});
