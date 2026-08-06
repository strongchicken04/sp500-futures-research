import type { ViewStyle } from 'react-native';

/** Warm storybook palette — creams, peach, soft pink, sage, sky. */
export const C = {
  bg: '#FFF7EC',
  bgDeep: '#FDEFDC',
  card: '#FFFDF8',
  cardWarm: '#FFF9F0',
  ink: '#54443A',
  inkSoft: '#93816F',
  inkFaint: '#BCAC99',
  line: '#F1E3CE',
  pink: '#F6C7D4',
  pinkDeep: '#E97C97',
  pinkDark: '#D95F80',
  peach: '#FFD9AE',
  peachDeep: '#F5A962',
  gold: '#F6C660',
  sage: '#BCDCAB',
  sageDeep: '#7FA86A',
  sky: '#BFE3F2',
  skyDeep: '#5D98B5',
  lavender: '#D9CCF0',
  lavenderDeep: '#9F8CC9',
  seaLight: '#D9EFF8',
  sea: '#C4E6F2',
  seaInk: '#2E6E88',
  white: '#FFFFFF',
  danger: '#CE5B4E',
};

/** Font families (loaded in app/_layout.tsx). Baloo 2 = display, Quicksand = body. */
export const F = {
  display: 'Baloo2_800ExtraBold',
  title: 'Baloo2_700Bold',
  semi: 'Baloo2_600SemiBold',
  bodyBold: 'Quicksand_700Bold',
  bodyMed: 'Quicksand_600SemiBold',
  body: 'Quicksand_500Medium',
  bodyLight: 'Quicksand_400Regular',
};

/** Corner radii */
export const R = { s: 14, m: 20, l: 26, xl: 34 };

export const shadowSoft: ViewStyle = {
  shadowColor: '#C9985E',
  shadowOpacity: 0.18,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 6 },
  elevation: 4,
};

export const shadowTiny: ViewStyle = {
  shadowColor: '#C9985E',
  shadowOpacity: 0.12,
  shadowRadius: 6,
  shadowOffset: { width: 0, height: 3 },
  elevation: 2,
};
