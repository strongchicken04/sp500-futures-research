/** Czech date formatting & pluralization — done by hand so it needs no Intl support. */

const DAYS = ['neděle', 'pondělí', 'úterý', 'středa', 'čtvrtek', 'pátek', 'sobota'];
const MONTHS_GENITIVE = [
  'ledna',
  'února',
  'března',
  'dubna',
  'května',
  'června',
  'července',
  'srpna',
  'září',
  'října',
  'listopadu',
  'prosince',
];
const MONTHS_SHORT = ['led', 'úno', 'bře', 'dub', 'kvě', 'čvn', 'čvc', 'srp', 'zář', 'říj', 'lis', 'pro'];

const two = (n: number) => String(n).padStart(2, '0');

/** "středa 6. srpna · 14:32" */
export function formatDateTime(ms: number): string {
  const d = new Date(ms);
  return `${DAYS[d.getDay()]} ${d.getDate()}. ${MONTHS_GENITIVE[d.getMonth()]} · ${d.getHours()}:${two(d.getMinutes())}`;
}

/** "6. srpna 2026" */
export function formatDateLong(ms: number): string {
  const d = new Date(ms);
  return `${d.getDate()}. ${MONTHS_GENITIVE[d.getMonth()]} ${d.getFullYear()}`;
}

/** For date bubbles: { day: "6.", month: "srp" } */
export function formatDayBubble(ms: number): { day: string; month: string } {
  const d = new Date(ms);
  return { day: `${d.getDate()}.`, month: MONTHS_SHORT[d.getMonth()] };
}

/** "14:32" */
export function formatTime(ms: number): string {
  const d = new Date(ms);
  return `${d.getHours()}:${two(d.getMinutes())}`;
}

/** Czech pluralization: plural(2, ['zápisek', 'zápisky', 'zápisků']) → "zápisky" */
export function plural(n: number, forms: [string, string, string]): string {
  if (n === 1) return forms[0];
  if (n >= 2 && n <= 4) return forms[1];
  return forms[2];
}

export function greetingForHour(h: number): string {
  if (h >= 5 && h < 10) return 'Dobré ráno';
  if (h >= 10 && h < 18) return 'Krásný den';
  if (h >= 18 && h < 22) return 'Hezký večer';
  return 'Dobrou noc';
}

/** Deterministic "random" pick that changes once a day. */
export function pickForToday<T>(items: T[]): T {
  const now = new Date();
  const dayIndex = Math.floor((now.getTime() - now.getTimezoneOffset() * 60000) / 86400000);
  return items[dayIndex % items.length];
}
