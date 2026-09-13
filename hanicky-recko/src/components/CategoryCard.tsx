import React, { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSpring,
  withTiming,
} from 'react-native-reanimated';

import { T } from '@/components/ui';
import type { Category } from '@/config/categories';
import { plural } from '@/lib/czech';

/** A big, friendly category card on the home screen. */
export function CategoryCard({
  category,
  count,
  index,
  onPress,
}: {
  category: Category;
  count: number;
  index: number;
  onPress: () => void;
}) {
  const float = useSharedValue(0);
  const scale = useSharedValue(1);

  useEffect(() => {
    float.value = withDelay(
      index * 240,
      withRepeat(withTiming(1, { duration: 2000, easing: Easing.inOut(Easing.sin) }), -1, true)
    );
  }, [float, index]);

  const style = useAnimatedStyle(() => ({
    transform: [{ translateY: float.value * -4 }, { scale: scale.value }],
  }));

  const caption =
    count === 0 ? 'zatím prázdné ✨' : `${count} ${plural(count, ['zápisek', 'zápisky', 'zápisků'])}`;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Kategorie ${category.name}`}
      onPressIn={() => {
        scale.value = withSpring(0.96, { damping: 18, stiffness: 300 });
      }}
      onPressOut={() => {
        scale.value = withSpring(1, { damping: 14, stiffness: 200 });
      }}
      onPress={onPress}
      style={styles.slot}>
      <Animated.View
        style={[styles.card, { backgroundColor: category.soft, shadowColor: category.accentDark }, style]}>
        <View style={styles.emojiBubble}>
          <Text style={{ fontSize: 30 }}>{category.emoji}</Text>
        </View>
        <T v="title" color={category.accentDark} numberOfLines={1} style={{ marginTop: 10, fontSize: 19 }}>
          {category.name}
        </T>
        <T v="tiny" color={category.accentDark} style={{ opacity: 0.75, marginTop: 1 }}>
          {caption}
        </T>
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  slot: { width: '47.7%' },
  card: {
    borderRadius: 28,
    paddingVertical: 18,
    paddingHorizontal: 16,
    minHeight: 140,
    justifyContent: 'center',
    shadowOpacity: 0.25,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  emojiBubble: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: '#FFFFFFC8',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
