import type { ViewStyle } from 'react-native';

/** Aegean palette — whitewashed walls, blue domes, sun and sea. */
export const C = {
  bg: '#F6FBFE',
  bgDeep: '#E7F4FB',
  card: '#FFFFFF',
  ink: '#2B4257',
  inkSoft: '#6D8598',
  inkFaint: '#A9BECC',
  line: '#DDEBF4',
  sea: '#BFE3F2',
  seaDeep: '#2E8BC0',
  seaInk: '#1B5E85',
  sky: '#DCF0FA',
  sun: '#F6C445',
  sunDeep: '#E0A21B',
  coral: '#E07A5F',
  coralDeep: '#B4543A',
  olive: '#8FA97B',
  bougain: '#D1618D',
  white: '#FFFFFF',
  danger: '#CE5B4E',
};

/** Fonts (loaded in app/_layout.tsx). Baloo 2 = display, Quicksand = body. */
export const F = {
  display: 'Baloo2_800ExtraBold',
  title: 'Baloo2_700Bold',
  semi: 'Baloo2_600SemiBold',
  bodyBold: 'Quicksand_700Bold',
  bodyMed: 'Quicksand_600SemiBold',
  body: 'Quicksand_500Medium',
  bodyLight: 'Quicksand_400Regular',
};

export const R = { s: 14, m: 20, l: 26, xl: 34 };

export const shadowSoft: ViewStyle = {
  shadowColor: '#2E8BC0',
  shadowOpacity: 0.18,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 6 },
  elevation: 4,
};

export const shadowTiny: ViewStyle = {
  shadowColor: '#2E8BC0',
  shadowOpacity: 0.12,
  shadowRadius: 6,
  shadowOffset: { width: 0, height: 3 },
  elevation: 2,
};
