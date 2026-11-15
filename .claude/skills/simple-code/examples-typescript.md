# Simple code examples: TypeScript

One before/after per practice. Every "after" block passes the house rules and the ESLint checks.

## 1. Push side effects to the edges

Before: randomness, the clock, and storage are tangled into the decision.

```ts
export async function createTrack(mood: string, userId: string, bucket: R2Bucket) {
  const bars = [];
  for (let bar = 0; bar < 16; bar++) {
    bars.push(Math.random() > 0.5 ? "i" : "iv");
  }
  await bucket.put(`${userId}/${Date.now()}.json`, JSON.stringify({ mood, bars }));
}
```

After: the pure rule lives in `src/core/arrangement.ts` and takes its random source as an argument.

```ts
/** Pick a chord for each bar from a seeded random source. */
export function arrangeBars(mood: Mood, barCount: number, nextRandom: () => number): Bar[] {
  const bars: Bar[] = [];
  for (let barNumber = 0; barNumber < barCount; barNumber += 1) {
    const chord = nextRandom() > 0.5 ? "i" : "iv";
    bars.push({ chord, hasDrums: mood === "combat" });
  }
  return bars;
}
```

After: the shell supplies randomness and time, then stores the result.

```ts
/** Arrange a track, then store it under the user's folder. */
export async function saveTrack(request: TrackRequest, bucket: R2Bucket, savedAt: Date) {
  const bars = arrangeBars(request.mood, 16, Math.random);
  const key = `${request.userId}/${savedAt.getTime()}.json`;
  await bucket.put(key, JSON.stringify(bars));
  return key;
}
```

## 2. Avoid hasty abstractions

Before: one caller's need became a flag on a shared function.

```ts
export function trackLabel(track: Track, forExport: boolean) {
  if (forExport) {
    return `${track.title}.wav`;
  }
  return track.title;
}
```

After: two small functions, each with one job.

```ts
/** Title shown in the track list. */
export function displayTitle(track: Track): string {
  return track.title;
}

/** File name used when a track is downloaded. */
export function downloadName(track: Track): string {
  return `${track.title}.wav`;
}
```

## 3. Build deep modules

Before: every caller must remember the engine's setup order.

```ts
const engine = new SynthEngine();
await engine.loadSamples(mood);
engine.connectReverb();
engine.schedule(bars);
const audio = await engine.render();
```

After: one call hides the order behind a small interface.

```ts
/** Render an arrangement to audio; hides the engine setup order. */
export async function renderTrack(arrangement: Arrangement): Promise<AudioBuffer> {
  const engine = new SynthEngine();
  await engine.loadSamples(arrangement.mood);
  engine.connectReverb();
  engine.schedule(arrangement.bars);
  return engine.render();
}
```

## 4. Keep behaviour local

Before: moods register themselves into a global map when some file imports them.

```ts
import "./moods/combat";
import "./moods/explore";

export const preset = moodRegistry.get(mood);
```

After: the lookup table is plain, visible, and constant.

```ts
import { combatPreset } from "./moods/combat";
import { explorePreset } from "./moods/explore";

const MOOD_PRESETS = { combat: combatPreset, explore: explorePreset } as const;

/** Look up the preset for a mood directly. */
export function presetFor(mood: keyof typeof MOOD_PRESETS) {
  return MOOD_PRESETS[mood];
}
```

## 5. Make state explicit and parse at the boundary

Before: three booleans that can contradict each other, and an unchecked string.

```ts
let isRendering = false;
let isDone = false;
let hasError = false;
const mood = new URL(request.url).searchParams.get("mood") as Mood;
```

After: one union type for render state, and one parse at the edge.

```ts
type RenderState =
  | { kind: "queued" }
  | { kind: "rendering"; progress: number }
  | { kind: "done"; fileKey: string }
  | { kind: "failed"; reason: string };

const MOODS = ["combat", "explore", "creepy"] as const;
type Mood = (typeof MOODS)[number];

/** Parse raw request input once; throw naming the bad value. */
export function parseMood(raw: unknown): Mood {
  const mood = MOODS.find((candidate) => candidate === raw);
  if (mood === undefined) {
    throw new Error(`Unknown mood: ${String(raw)}`);
  }
  return mood;
}
```

## 6. Flatten control flow

Before: nested branches and an unnamed compound condition.

```ts
function canExport(user: User, count: number) {
  if (!user.isBanned) {
    if (user.plan === "paid" || count < 3) {
      return true;
    } else {
      return false;
    }
  }
  return false;
}
```

After: a guard clause, then named conditions.

```ts
/** Decide whether a user may export another track this month. */
export function canExport(user: User, exportsThisMonth: number): boolean {
  if (user.isBanned) {
    return false;
  }
  const isPaid = user.plan === "paid";
  const hasFreeExportsLeft = exportsThisMonth < FREE_EXPORT_LIMIT;
  return isPaid || hasFreeExportsLeft;
}
```

## 7. Write boring code that fails loudly

Before: a missing file quietly becomes `null`, and the error is lost.

```ts
async function loadTrack(bucket: R2Bucket, key: string) {
  try {
    return await (await bucket.get(key))!.arrayBuffer();
  } catch {
    return null;
  }
}
```

After: the failure names the bad value and reaches the caller.

```ts
/** Load a saved track, or throw naming the missing key. */
export async function loadTrack(bucket: R2Bucket, key: string): Promise<ArrayBuffer> {
  const stored = await bucket.get(key);
  if (stored === null) {
    throw new Error(`Track not found in storage: ${key}`);
  }
  return stored.arrayBuffer();
}
```
