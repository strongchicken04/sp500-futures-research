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
import type { Activity } from '@/config/activities';
import { plural } from '@/lib/czech';

/** A floating island on the home-screen sea. */
export function IslandCard({
  activity,
  count,
  index,
  onPress,
}: {
  activity: Activity;
  count: number;
  index: number;
  onPress: () => void;
}) {
  const float = useSharedValue(0);
  const scale = useSharedValue(1);

  useEffect(() => {
    float.value = withDelay(
      index * 260,
      withRepeat(withTiming(1, { duration: 1900, easing: Easing.inOut(Easing.sin) }), -1, true)
    );
  }, [float, index]);

  const style = useAnimatedStyle(() => ({
    transform: [{ translateY: float.value * -4.5 }, { scale: scale.value }],
  }));

  const caption =
    count === 0 ? 'první zápisek čeká ✨' : `${count} ${plural(count, ['zápisek', 'zápisky', 'zápisků'])}`;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Ostrůvek ${activity.name}`}
      onPressIn={() => {
        scale.value = withSpring(0.95, { damping: 18, stiffness: 300 });
      }}
      onPressOut={() => {
        scale.value = withSpring(1, { damping: 14, stiffness: 200 });
      }}
      onPress={onPress}
      style={styles.slot}>
      <Animated.View
        style={[styles.card, { backgroundColor: activity.soft, shadowColor: activity.accentDark }, style]}>
        <View style={styles.emojiBubble}>
          <Text style={{ fontSize: 26 }}>{activity.emoji}</Text>
        </View>
        <T v="heading" color={activity.accentDark} numberOfLines={1} style={{ marginTop: 8 }}>
          {activity.name}
        </T>
        <T v="tiny" color={activity.accentDark} style={{ opacity: 0.75, marginTop: 1 }}>
          {caption}
        </T>
        {/* little sandy beach at the foot of the island */}
        <View style={[styles.beach, { backgroundColor: '#FFFFFF55' }]} />
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  slot: { width: '47.7%' },
  card: {
    borderRadius: 26,
    paddingVertical: 14,
    paddingHorizontal: 14,
    minHeight: 122,
    overflow: 'hidden',
    shadowOpacity: 0.28,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  emojiBubble: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: '#FFFFFFB8',
    alignItems: 'center',
    justifyContent: 'center',
  },
  beach: {
    position: 'absolute',
    bottom: -26,
    left: -14,
    right: -14,
    height: 44,
    borderTopLeftRadius: 60,
    borderTopRightRadius: 80,
  },
});
