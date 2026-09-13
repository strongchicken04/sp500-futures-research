import AsyncStorage from '@react-native-async-storage/async-storage';

/** All data lives locally on the device in AsyncStorage as JSON. */
export const STORAGE_KEYS = {
  entries: 'hanicky-recko.entries.v1',
} as const;

export async function loadJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (raw == null) return fallback;
    return JSON.parse(raw) as T;
  } catch (e) {
    console.warn(`loadJSON(${key}) failed`, e);
    return fallback;
  }
}

export async function saveJSON(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn(`saveJSON(${key}) failed`, e);
  }
}
