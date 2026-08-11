/**
 * Menstrual-cycle math. Data is simply a sorted list of ISO dates (YYYY-MM-DD)
 * of period days; everything else (episodes, cycle lengths, averages and the
 * next-period prediction) is derived. All local, nothing leaves the device.
 */

const two = (n: number) => String(n).padStart(2, '0');

export function toISO(d: Date): string {
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`;
}

export function fromISO(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function addDaysISO(iso: string, days: number): string {
  const d = fromISO(iso);
  d.setDate(d.getDate() + days);
  return toISO(d);
}

/** Whole days from `a` to `b` (positive when b is later). */
export function diffDaysISO(a: string, b: string): number {
  return Math.round((fromISO(b).getTime() - fromISO(a).getTime()) / 86400000);
}

export type Episode = { start: string; length: number };

/** Groups sorted period days into consecutive episodes (one per period). */
export function episodesFromDays(sortedDays: string[]): Episode[] {
  const out: Episode[] = [];
  for (const day of sortedDays) {
    const last = out[out.length - 1];
    if (last && diffDaysISO(addDaysISO(last.start, last.length - 1), day) === 1) {
      last.length += 1;
    } else {
      out.push({ start: day, length: 1 });
    }
  }
  return out;
}

export type CycleStats = {
  hasData: boolean;
  lastStart?: string;
  /** 1-based day of the current cycle (only when the data is fresh) */
  dayOfCycle?: number;
  avgCycleDays: number;
  /** true once at least two period starts exist */
  avgCycleKnown: boolean;
  avgPeriodDays: number;
  predictedStart?: string;
  /** predicted period days to mark in the calendar */
  predictedDays: string[];
  /** last start is too long ago for a trustworthy prediction */
  predictionStale: boolean;
};

const DEFAULT_CYCLE = 28;
const DEFAULT_PERIOD = 5;

export function computeStats(days: string[], todayISO: string): CycleStats {
  const sorted = [...days].sort();
  const eps = episodesFromDays(sorted);
  if (eps.length === 0) {
    return {
      hasData: false,
      avgCycleDays: DEFAULT_CYCLE,
      avgCycleKnown: false,
      avgPeriodDays: DEFAULT_PERIOD,
      predictedDays: [],
      predictionStale: false,
    };
  }

  // Cycle lengths between consecutive starts, keeping only plausible ones.
  const starts = eps.map((e) => e.start);
  const lengths: number[] = [];
  for (let i = 1; i < starts.length; i++) {
    const len = diffDaysISO(starts[i - 1], starts[i]);
    if (len >= 15 && len <= 60) lengths.push(len);
  }
  const recent = lengths.slice(-6);
  const avgCycleDays =
    recent.length > 0 ? Math.round(recent.reduce((a, b) => a + b, 0) / recent.length) : DEFAULT_CYCLE;

  const periodLens = eps.map((e) => Math.min(e.length, 10)).slice(-6);
  const avgPeriodDays = Math.min(
    10,
    Math.max(2, Math.round(periodLens.reduce((a, b) => a + b, 0) / periodLens.length) || DEFAULT_PERIOD)
  );

  const lastStart = starts[starts.length - 1];
  const sinceStart = diffDaysISO(lastStart, todayISO);
  const predictionStale = sinceStart > avgCycleDays * 2 + 7;
  const dayOfCycle = sinceStart >= 0 && !predictionStale ? sinceStart + 1 : undefined;

  const predictedStart = predictionStale ? undefined : addDaysISO(lastStart, avgCycleDays);
  const predictedDays: string[] = [];
  if (predictedStart) {
    for (let i = 0; i < avgPeriodDays; i++) predictedDays.push(addDaysISO(predictedStart, i));
  }

  return {
    hasData: true,
    lastStart,
    dayOfCycle,
    avgCycleDays,
    avgCycleKnown: recent.length > 0,
    avgPeriodDays,
    predictedStart,
    predictedDays,
    predictionStale,
  };
}
