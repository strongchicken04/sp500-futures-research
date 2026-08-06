/** Small collision-safe-enough id for local, single-device data. */
export function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}
