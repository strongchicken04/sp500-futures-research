import React, { useEffect, useMemo, useRef, useState } from 'react';
import Animated, {
  Easing,
  useAnimatedProps,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Circle, Defs, Ellipse, G, LinearGradient, Path, RadialGradient, Stop } from 'react-native-svg';

import { hsl } from '@/lib/color';
import type { CosmeticInstance } from '@/lib/xp';

const AnimatedG = Animated.createAnimatedComponent(G);

/* ------------------------------------------------------------------ */
/* Math helpers                                                        */
/* ------------------------------------------------------------------ */

const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
const smooth = (t: number) => t * t * (3 - 2 * t);
/** eased 0→1 as level moves from `from` to `to` */
const ramp = (level: number, from: number, to: number) => smooth(clamp01((level - from) / (to - from)));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

const VB_W = 240;
const VB_H = 244;
export const PET_ASPECT = VB_H / VB_W;

/* ------------------------------------------------------------------ */
/* Small path builders                                                 */
/* ------------------------------------------------------------------ */

function earPath(cx: number, baseY: number, w: number, h: number, round: number, lean: number): string {
  const half = w / 2;
  const tipX = cx + lean;
  const tipY = baseY - h;
  const bulge = round * 9;
  const cY = baseY - h * 0.6;
  return `M ${cx - half} ${baseY} Q ${cx - half - bulge} ${cY} ${tipX} ${tipY} Q ${cx + half + bulge} ${cY} ${cx + half} ${baseY} Z`;
}

function starPath(cx: number, cy: number, rOuter: number, points = 4, inner = 0.42): string {
  const rInner = rOuter * inner;
  let d = '';
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? rOuter : rInner;
    const a = (Math.PI * i) / points - Math.PI / 2;
    const x = cx + r * Math.cos(a);
    const y = cy + r * Math.sin(a);
    d += `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)} `;
  }
  return d + 'Z';
}

function heartPath(cx: number, cy: number, s: number): string {
  return (
    `M ${cx} ${cy + s * 0.9} ` +
    `C ${cx - s * 1.25} ${cy + s * 0.05} ${cx - s * 0.75} ${cy - s * 0.8} ${cx} ${cy - s * 0.25} ` +
    `C ${cx + s * 0.75} ${cy - s * 0.8} ${cx + s * 1.25} ${cy + s * 0.05} ${cx} ${cy + s * 0.9} Z`
  );
}

function crescentPath(cx: number, cy: number, r: number): string {
  const x = cx + r * 0.35;
  return (
    `M ${x} ${cy - r} ` +
    `A ${r} ${r} 0 1 0 ${x} ${cy + r} ` +
    `A ${r * 1.35} ${r * 1.35} 0 0 1 ${x} ${cy - r} Z`
  );
}

/* ------------------------------------------------------------------ */
/* The look — every visual parameter derived from the level            */
/* ------------------------------------------------------------------ */

export function buildPetLook(levelRaw: number) {
  const level = Math.max(0, Math.floor(levelRaw));

  const catT = ramp(level, 0, 10); // hamster → cat master morph
  const earT = ramp(level, 2, 9); // round nubs → tall pointy ears
  const tailT = ramp(level, 3, 12); // stub → long curled tail
  const whiskerT = ramp(level, 4, 10); // whiskers appear & lengthen
  const eyeT = ramp(level, 0, 14); // eyes grow more expressive
  const stripesT = ramp(level, 8, 11); // tabby stripes
  const patchT = ramp(level, 14, 16); // soft patches
  const shimmerT = ramp(level, 20, 24); // gradient shimmer on fur

  // Fur: warm hamster gold → creamy ginger cat; after the "krásná kočka"
  // milestone the hue drifts slowly through a pastel rainbow — always pretty,
  // never done.
  let hue = lerp(33, 27, catT);
  let sat = lerp(52, 56, catT);
  let lig = lerp(68, 75, catT);
  if (level > 12) {
    hue = (27 + (level - 12) * 16) % 360;
    sat = 48;
    lig = 76;
  }
  const fur = hsl(hue, sat, lig);
  const furLight = hsl(hue, Math.max(26, sat - 10), Math.min(93, lig + 13));
  const furDark = hsl(hue, sat + 4, lig - 17);

  const headR = lerp(55, 47, catT);
  const headCy = lerp(118, 96, catT);
  const bodyRx = lerp(59, 44, catT);
  const bodyRy = lerp(47, 57, catT);
  const bodyCy = lerp(152, 170, catT);

  return {
    level,
    catT,
    earT,
    tailT,
    whiskerT,
    eyeT,
    stripesT,
    patchT,
    shimmerT,
    fur,
    furLight,
    furDark,
    headR,
    headCy,
    bodyRx,
    bodyRy,
    bodyCy,
    earBaseY: headCy - headR * 0.55,
    earOffX: headR * lerp(0.5, 0.58, earT),
    earW: lerp(27, 33, earT),
    earH: lerp(37, 56, earT),
    eyeOffX: headR * 0.4,
    eyeY: headCy - headR * 0.02,
    eyeR: lerp(8, 11, eyeT),
    noseY: headCy + headR * 0.2,
  };
}

export type PetLook = ReturnType<typeof buildPetLook>;

/* ------------------------------------------------------------------ */
/* Cosmetic bits                                                       */
/* ------------------------------------------------------------------ */

const VARIANT_PALETTES: [string, string][] = [
  ['#E8768F', '#F7C3CF'],
  ['#639FD1', '#BFDCF2'],
  ['#A98BD3', '#DACAF1'],
  ['#E5A23C', '#F7DCA6'],
  ['#5FB894', '#BFE7D6'],
];

const palFor = (variant: number) => VARIANT_PALETTES[variant % VARIANT_PALETTES.length];

function Bow({ cx, cy, pal }: { cx: number; cy: number; pal: [string, string] }) {
  const wing = (dir: 1 | -1) =>
    `M ${cx} ${cy} Q ${cx + dir * 5} ${cy - 9} ${cx + dir * 13} ${cy - 7} ` +
    `Q ${cx + dir * 16} ${cy - 1} ${cx + dir * 11} ${cy + 4} Q ${cx + dir * 5} ${cy + 6} ${cx} ${cy} Z`;
  return (
    <G>
      <Path d={wing(-1)} fill={pal[0]} />
      <Path d={wing(1)} fill={pal[0]} />
      <Circle cx={cx} cy={cy} r={3.6} fill={pal[1]} />
    </G>
  );
}

function Flower({ cx, cy, pal }: { cx: number; cy: number; pal: [string, string] }) {
  const petals = [0, 1, 2, 3, 4].map((i) => {
    const a = (i / 5) * Math.PI * 2 - Math.PI / 2;
    return <Circle key={i} cx={cx + 5.6 * Math.cos(a)} cy={cy + 5.6 * Math.sin(a)} r={4.1} fill={pal[1]} />;
  });
  return (
    <G>
      {petals}
      <Circle cx={cx} cy={cy} r={3.4} fill="#F6C660" />
    </G>
  );
}

function Crown({ cx, y }: { cx: number; y: number }) {
  const d =
    `M ${cx - 13} ${y} L ${cx - 13} ${y - 9} L ${cx - 6} ${y - 4} L ${cx} ${y - 12} ` +
    `L ${cx + 6} ${y - 4} L ${cx + 13} ${y - 9} L ${cx + 13} ${y} Z`;
  return (
    <G>
      <Path d={d} fill="#F4C14F" stroke="#DBA02F" strokeWidth={1} strokeLinejoin="round" />
      <Circle cx={cx - 13} cy={y - 10.5} r={1.8} fill="#FFE59A" />
      <Circle cx={cx} cy={y - 13.5} r={1.8} fill="#FFE59A" />
      <Circle cx={cx + 13} cy={y - 10.5} r={1.8} fill="#FFE59A" />
    </G>
  );
}

function Scarf({ look, pal }: { look: PetLook; pal: [string, string] }) {
  const y = look.bodyCy - look.bodyRy * 0.68;
  const half = look.bodyRx * 0.56;
  return (
    <G>
      <Path
        d={`M ${120 - half} ${y} Q 120 ${y + 13} ${120 + half} ${y}`}
        stroke={pal[0]}
        strokeWidth={11}
        strokeLinecap="round"
        fill="none"
      />
      <Path
        d={`M ${120 + half * 0.45} ${y + 7} q 3 9 -1 17`}
        stroke={pal[0]}
        strokeWidth={8.5}
        strokeLinecap="round"
        fill="none"
      />
      <Circle cx={120 + half * 0.42} cy={y + 26} r={2.6} fill={pal[1]} />
    </G>
  );
}

function StarBuddy({ pal }: { pal: [string, string] }) {
  return (
    <G>
      <Path d={starPath(198, 62, 9, 4)} fill="#F8D66B" />
      <Path d={starPath(211, 82, 4.5, 4)} fill={pal[1]} />
    </G>
  );
}

function MoonBuddy() {
  return (
    <G>
      <Path d={crescentPath(42, 58, 10)} fill="#F8E3A2" />
      <Path d={starPath(58, 74, 3.4, 4)} fill="#F8E3A2" />
    </G>
  );
}

function Butterfly({ look, pal }: { look: PetLook; pal: [string, string] }) {
  const bx = 120 + look.headR * 0.98;
  const by = look.headCy - look.headR * 0.9;
  return (
    <G>
      <Circle cx={bx - 4.6} cy={by - 3} r={4.6} fill={pal[0]} opacity={0.92} />
      <Circle cx={bx - 3.6} cy={by + 3.6} r={3.3} fill={pal[1]} />
      <Circle cx={bx + 4.6} cy={by - 3} r={4.6} fill={pal[0]} opacity={0.92} />
      <Circle cx={bx + 3.6} cy={by + 3.6} r={3.3} fill={pal[1]} />
      <Ellipse cx={bx} cy={by} rx={1.5} ry={5.6} fill="#6B5344" />
    </G>
  );
}

function HeartBuddy({ pal }: { pal: [string, string] }) {
  return (
    <G>
      <Path d={heartPath(34, 148, 7)} fill="#F2849E" />
      <Path d={heartPath(48, 166, 4.2)} fill={pal[1]} opacity={0.9} />
    </G>
  );
}

/** Gently twinkling ambient sparkle. */
function Twinkle({ cx, cy, r, delay }: { cx: number; cy: number; r: number; delay: number }) {
  const o = useSharedValue(0.25);
  useEffect(() => {
    o.value = withDelay(
      delay,
      withRepeat(
        withSequence(
          withTiming(0.95, { duration: 900, easing: Easing.inOut(Easing.quad) }),
          withTiming(0.2, { duration: 900, easing: Easing.inOut(Easing.quad) })
        ),
        -1,
        false
      )
    );
  }, [delay, o]);
  const animatedProps = useAnimatedProps(() => ({ opacity: o.value }));
  return <AnimatedG animatedProps={animatedProps}><Path d={starPath(cx, cy, r, 4)} fill="#FFDf8E" /></AnimatedG>;
}

/* ------------------------------------------------------------------ */
/* The pet                                                             */
/* ------------------------------------------------------------------ */

export type PetMood = 'idle' | 'happy';

type Props = {
  level: number;
  size: number;
  cosmetics?: CosmeticInstance[];
  mood?: PetMood;
  /** enable idle bobbing/breathing */
  animate?: boolean;
  /** bump this number to trigger a happy wiggle */
  happyTick?: number;
};

export function PetAvatar({ level, size, cosmetics = [], mood = 'idle', animate = true, happyTick = 0 }: Props) {
  const look = useMemo(() => buildPetLook(level), [level]);
  const [blink, setBlink] = useState(false);

  /* --- blinking (skipped while happy — happy eyes are closed anyway) --- */
  useEffect(() => {
    let alive = true;
    let t1: ReturnType<typeof setTimeout>;
    let t2: ReturnType<typeof setTimeout>;
    const loop = () => {
      t1 = setTimeout(() => {
        if (!alive) return;
        setBlink(true);
        t2 = setTimeout(() => {
          if (!alive) return;
          setBlink(false);
          loop();
        }, 140);
      }, 2400 + Math.random() * 2800);
    };
    loop();
    return () => {
      alive = false;
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

  /* --- idle bob + breathe, happy wiggle --- */
  const bob = useSharedValue(0);
  const breathe = useSharedValue(0);
  const wiggle = useSharedValue(0);
  const bump = useSharedValue(0);

  useEffect(() => {
    if (!animate) return;
    bob.value = withRepeat(withTiming(1, { duration: 1700, easing: Easing.inOut(Easing.sin) }), -1, true);
    breathe.value = withDelay(
      300,
      withRepeat(withTiming(1, { duration: 2300, easing: Easing.inOut(Easing.sin) }), -1, true)
    );
  }, [animate, bob, breathe]);

  const prevTick = useRef(happyTick);
  useEffect(() => {
    if (happyTick === prevTick.current) return;
    prevTick.current = happyTick;
    wiggle.value = withSequence(
      withTiming(1, { duration: 100 }),
      withRepeat(withSequence(withTiming(-1, { duration: 140 }), withTiming(1, { duration: 140 })), 3, true),
      withSpring(0, { damping: 9, stiffness: 160 })
    );
    bump.value = withSequence(
      withSpring(1, { damping: 7, stiffness: 260 }),
      withDelay(450, withSpring(0, { damping: 14, stiffness: 120 }))
    );
  }, [happyTick, wiggle, bump]);

  const animStyle = useAnimatedStyle(() => ({
    transform: [
      { translateY: bob.value * -5 },
      { rotate: `${wiggle.value * 4}deg` },
      { scale: 1 + breathe.value * 0.013 + bump.value * 0.05 },
    ],
  }));

  /* --- cosmetics to show: latest 2 wearables + latest 2 ambient + glow --- */
  const wearables = cosmetics.filter((c) => ['bow', 'flower', 'crown', 'scarf'].includes(c.id)).slice(-2);
  const ambient = cosmetics
    .filter((c) => ['star', 'butterfly', 'heart', 'moon'].includes(c.id))
    .slice(-2);
  const sparkles = cosmetics.filter((c) => c.id === 'sparkles').slice(-1);
  const hasGlow = cosmetics.some((c) => c.id === 'glow');

  const happy = mood === 'happy';
  const l = look;

  /* --- face pieces --- */
  const eyeL = 120 - l.eyeOffX;
  const eyeR2 = 120 + l.eyeOffX;
  const mouthY = l.noseY + 7.5;

  const eyes = happy ? (
    <G>
      <Path
        d={`M ${eyeL - 8} ${l.eyeY + 2} Q ${eyeL} ${l.eyeY - 6} ${eyeL + 8} ${l.eyeY + 2}`}
        stroke="#4A3730"
        strokeWidth={3.4}
        strokeLinecap="round"
        fill="none"
      />
      <Path
        d={`M ${eyeR2 - 8} ${l.eyeY + 2} Q ${eyeR2} ${l.eyeY - 6} ${eyeR2 + 8} ${l.eyeY + 2}`}
        stroke="#4A3730"
        strokeWidth={3.4}
        strokeLinecap="round"
        fill="none"
      />
    </G>
  ) : blink ? (
    <G>
      <Path
        d={`M ${eyeL - 7} ${l.eyeY} Q ${eyeL} ${l.eyeY + 4} ${eyeL + 7} ${l.eyeY}`}
        stroke="#4A3730"
        strokeWidth={3}
        strokeLinecap="round"
        fill="none"
      />
      <Path
        d={`M ${eyeR2 - 7} ${l.eyeY} Q ${eyeR2} ${l.eyeY + 4} ${eyeR2 + 7} ${l.eyeY}`}
        stroke="#4A3730"
        strokeWidth={3}
        strokeLinecap="round"
        fill="none"
      />
    </G>
  ) : (
    <G>
      {[eyeL, eyeR2].map((ex) => (
        <G key={ex}>
          <Circle cx={ex} cy={l.eyeY} r={l.eyeR} fill="#4A3730" />
          <Circle cx={ex - l.eyeR * 0.3} cy={l.eyeY - l.eyeR * 0.32} r={l.eyeR * 0.34} fill="#FFFFFF" />
          {l.level >= 6 && (
            <Circle cx={ex + l.eyeR * 0.36} cy={l.eyeY + l.eyeR * 0.3} r={l.eyeR * 0.16} fill="#FFFFFF" opacity={0.9} />
          )}
        </G>
      ))}
    </G>
  );

  const mouth = happy ? (
    <G>
      <Path
        d={`M ${120 - 7.5} ${mouthY - 1} Q 120 ${mouthY + 9.5} ${120 + 7.5} ${mouthY - 1} Q 120 ${mouthY + 3} ${120 - 7.5} ${mouthY - 1} Z`}
        fill="#9C5B50"
      />
      <Ellipse cx={120} cy={mouthY + 3.6} rx={3.6} ry={2.3} fill="#F390A5" />
    </G>
  ) : (
    <Path
      d={`M ${120 - 8} ${mouthY} Q ${120 - 4} ${mouthY + 4} 120 ${mouthY} Q ${120 + 4} ${mouthY + 4} ${120 + 8} ${mouthY}`}
      stroke="#8A6A52"
      strokeWidth={2.2}
      strokeLinecap="round"
      fill="none"
    />
  );

  /* --- whiskers --- */
  const whiskerLen = 30 * l.whiskerT;
  const whiskers =
    l.whiskerT > 0.05 ? (
      <G opacity={Math.min(1, l.whiskerT * 1.4)}>
        {[-1, 1].map((dir) => {
          const ox = 120 + dir * l.headR * 0.52;
          const oy = l.headCy + l.headR * 0.28;
          return (
            <G key={dir}>
              {[-7, 0, 7].map((dy) => (
                <Path
                  key={dy}
                  d={`M ${ox} ${oy + dy * 0.4} Q ${ox + dir * whiskerLen * 0.6} ${oy + dy * 0.75 - 2} ${
                    ox + dir * whiskerLen
                  } ${oy + dy}`}
                  stroke="#B5987C"
                  strokeWidth={1.8}
                  strokeLinecap="round"
                  fill="none"
                />
              ))}
            </G>
          );
        })}
      </G>
    ) : null;

  /* --- tail --- */
  const tailSx = 120 + l.bodyRx * 0.78;
  const tailSy = l.bodyCy + l.bodyRy * 0.33;
  const tail =
    l.tailT < 0.12 ? (
      <Circle cx={tailSx + 4} cy={tailSy - 2} r={6} fill={l.furDark} />
    ) : (
      <G>
        <Path
          d={`M ${tailSx} ${tailSy} C ${tailSx + 40 * l.tailT} ${tailSy + 12 * l.tailT} ${
            tailSx + 56 * l.tailT
          } ${tailSy - 36 * l.tailT} ${tailSx + 34 * l.tailT} ${tailSy - 70 * l.tailT}`}
          stroke={l.furDark}
          strokeWidth={lerp(9, 14, l.tailT)}
          strokeLinecap="round"
          fill="none"
        />
        {l.tailT > 0.5 && (
          <Circle
            cx={tailSx + 34 * l.tailT}
            cy={tailSy - 70 * l.tailT}
            r={lerp(9, 14, l.tailT) * 0.55}
            fill={l.furLight}
            opacity={ramp(l.tailT, 0.5, 0.8)}
          />
        )}
      </G>
    );

  /* --- stripes / patches / shimmer --- */
  const stripes =
    l.stripesT > 0.02 ? (
      <G opacity={l.stripesT * 0.5} stroke={l.furDark} strokeWidth={5} strokeLinecap="round" fill="none">
        <Path d={`M 120 ${l.headCy - l.headR + 7} q 1 6 0 12`} />
        <Path d={`M 107 ${l.headCy - l.headR + 11} q 1 5 0 10`} />
        <Path d={`M 133 ${l.headCy - l.headR + 11} q -1 5 0 10`} />
        <Path d={`M ${120 - l.bodyRx * 0.9} ${l.bodyCy - 8} q 9 3 12 12`} />
        <Path d={`M ${120 + l.bodyRx * 0.9} ${l.bodyCy - 8} q -9 3 -12 12`} />
      </G>
    ) : null;

  const patches =
    l.patchT > 0.02 ? (
      <G opacity={l.patchT}>
        <Ellipse
          cx={120 + l.headR * 0.38}
          cy={l.headCy - l.headR * 0.3}
          rx={l.headR * 0.3}
          ry={l.headR * 0.24}
          fill={l.furDark}
          opacity={0.22}
        />
        <Ellipse
          cx={120 - l.bodyRx * 0.45}
          cy={l.bodyCy + l.bodyRy * 0.18}
          rx={14}
          ry={10}
          fill={l.furDark}
          opacity={0.2}
        />
      </G>
    ) : null;

  const pouchScale = 1 - l.catT * 0.5;
  const blushOpacity = happy ? 0.55 : 0.38;

  return (
    <Animated.View style={[{ width: size, height: size * PET_ASPECT }, animate ? animStyle : null]}>
      <Svg width={size} height={size * PET_ASPECT} viewBox={`0 0 ${VB_W} ${VB_H}`}>
        <Defs>
          <RadialGradient id="glowg" cx="50%" cy="50%" r="50%">
            <Stop offset="0" stopColor="#FFD98E" stopOpacity={0.7} />
            <Stop offset="0.6" stopColor="#FFE7B8" stopOpacity={0.32} />
            <Stop offset="1" stopColor="#FFE7B8" stopOpacity={0} />
          </RadialGradient>
          <LinearGradient id="shimmer" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor="#FFFFFF" stopOpacity={0.55} />
            <Stop offset="0.55" stopColor="#FFFFFF" stopOpacity={0.08} />
            <Stop offset="1" stopColor="#FFFFFF" stopOpacity={0} />
          </LinearGradient>
        </Defs>

        {/* aura */}
        {hasGlow && <Circle cx={120} cy={lerp(140, 136, l.catT)} r={112} fill="url(#glowg)" />}

        {/* ground shadow */}
        <Ellipse
          cx={120}
          cy={l.bodyCy + l.bodyRy + 6}
          rx={l.bodyRx * 0.92}
          ry={7}
          fill="#8A6A4A"
          opacity={0.13}
        />

        {/* tail behind the body */}
        {tail}

        {/* ears (behind head) */}
        <G>
          <Path
            d={earPath(120 - l.earOffX, l.earBaseY, l.earW, l.earH, 1 - l.earT, -4 * l.earT)}
            fill={l.fur}
          />
          <Path
            d={earPath(120 + l.earOffX, l.earBaseY, l.earW, l.earH, 1 - l.earT, 4 * l.earT)}
            fill={l.fur}
          />
          <Path
            d={earPath(120 - l.earOffX, l.earBaseY - 3, l.earW * 0.52, l.earH * 0.58, 1 - l.earT, -2.5 * l.earT)}
            fill="#F5A8B8"
            opacity={0.85}
          />
          <Path
            d={earPath(120 + l.earOffX, l.earBaseY - 3, l.earW * 0.52, l.earH * 0.58, 1 - l.earT, 2.5 * l.earT)}
            fill="#F5A8B8"
            opacity={0.85}
          />
        </G>

        {/* haunches (cat sitting) */}
        {l.catT > 0.15 && (
          <G opacity={l.catT}>
            <Ellipse
              cx={120 - l.bodyRx * 0.78}
              cy={l.bodyCy + l.bodyRy * 0.42}
              rx={l.bodyRx * 0.42}
              ry={l.bodyRy * 0.34}
              fill={l.fur}
            />
            <Ellipse
              cx={120 + l.bodyRx * 0.78}
              cy={l.bodyCy + l.bodyRy * 0.42}
              rx={l.bodyRx * 0.42}
              ry={l.bodyRy * 0.34}
              fill={l.fur}
            />
          </G>
        )}

        {/* body + belly */}
        <Ellipse cx={120} cy={l.bodyCy} rx={l.bodyRx} ry={l.bodyRy} fill={l.fur} />
        <Ellipse
          cx={120}
          cy={l.bodyCy + l.bodyRy * 0.18}
          rx={l.bodyRx * 0.58}
          ry={l.bodyRy * 0.6}
          fill={l.furLight}
        />

        {/* front paws */}
        <G>
          <Ellipse cx={105} cy={l.bodyCy + l.bodyRy - 9} rx={12.5} ry={9} fill={l.fur} />
          <Ellipse cx={135} cy={l.bodyCy + l.bodyRy - 9} rx={12.5} ry={9} fill={l.fur} />
          <Path
            d={`M 105 ${l.bodyCy + l.bodyRy - 12} v 5 M 135 ${l.bodyCy + l.bodyRy - 12} v 5`}
            stroke={l.furDark}
            strokeWidth={1.5}
            strokeLinecap="round"
            opacity={0.4}
          />
        </G>

        {/* head + hamster cheek pouches */}
        <Circle cx={120} cy={l.headCy} r={l.headR} fill={l.fur} />
        {l.catT < 0.98 && (
          <G opacity={1 - l.catT}>
            <Ellipse
              cx={120 - l.headR * 0.6}
              cy={l.headCy + l.headR * 0.32}
              rx={l.headR * 0.36 * pouchScale}
              ry={l.headR * 0.3 * pouchScale}
              fill={l.fur}
            />
            <Ellipse
              cx={120 + l.headR * 0.6}
              cy={l.headCy + l.headR * 0.32}
              rx={l.headR * 0.36 * pouchScale}
              ry={l.headR * 0.3 * pouchScale}
              fill={l.fur}
            />
            <Ellipse
              cx={120 - l.headR * 0.58}
              cy={l.headCy + l.headR * 0.34}
              rx={l.headR * 0.26 * pouchScale}
              ry={l.headR * 0.2 * pouchScale}
              fill={l.furLight}
              opacity={0.6}
            />
            <Ellipse
              cx={120 + l.headR * 0.58}
              cy={l.headCy + l.headR * 0.34}
              rx={l.headR * 0.26 * pouchScale}
              ry={l.headR * 0.2 * pouchScale}
              fill={l.furLight}
              opacity={0.6}
            />
          </G>
        )}

        {stripes}
        {patches}

        {/* shimmer overlay */}
        {l.shimmerT > 0.02 && (
          <Ellipse
            cx={118}
            cy={l.bodyCy - 14}
            rx={l.bodyRx * 0.98}
            ry={l.bodyRy * 1.15}
            fill="url(#shimmer)"
            opacity={0.4 * l.shimmerT}
          />
        )}

        {/* muzzle (appears with the cat) */}
        {l.catT > 0.2 && (
          <Ellipse
            cx={120}
            cy={l.headCy + l.headR * 0.3}
            rx={l.headR * 0.3}
            ry={l.headR * 0.22}
            fill={l.furLight}
            opacity={l.catT * 0.9}
          />
        )}

        {/* blush */}
        <Circle cx={120 - l.headR * 0.55} cy={l.headCy + l.headR * 0.26} r={l.headR * 0.15} fill="#F58FA8" opacity={blushOpacity} />
        <Circle cx={120 + l.headR * 0.55} cy={l.headCy + l.headR * 0.26} r={l.headR * 0.15} fill="#F58FA8" opacity={blushOpacity} />

        {/* face */}
        {eyes}
        <Path
          d={`M ${120 - 4.5} ${l.noseY - 2} Q 120 ${l.noseY - 5} ${120 + 4.5} ${l.noseY - 2} Q ${120 + 4.5} ${l.noseY + 1.5} 120 ${l.noseY + 3.5} Q ${120 - 4.5} ${l.noseY + 1.5} ${120 - 4.5} ${l.noseY - 2} Z`}
          fill="#E7818F"
        />
        {mouth}
        {whiskers}

        {/* wearable cosmetics */}
        {wearables.map((c) => {
          const pal = palFor(c.variant);
          if (c.id === 'bow') return <Bow key={c.key} cx={120 - l.headR * 0.58} cy={l.headCy - l.headR * 0.62} pal={pal} />;
          if (c.id === 'flower') return <Flower key={c.key} cx={120 + l.headR * 0.6} cy={l.headCy - l.headR * 0.58} pal={pal} />;
          if (c.id === 'crown') return <Crown key={c.key} cx={120} y={l.headCy - l.headR - 4} />;
          return <Scarf key={c.key} look={l} pal={pal} />;
        })}

        {/* ambient buddies */}
        {ambient.map((c) => {
          const pal = palFor(c.variant);
          if (c.id === 'star') return <StarBuddy key={c.key} pal={pal} />;
          if (c.id === 'moon') return <MoonBuddy key={c.key} />;
          if (c.id === 'butterfly') return <Butterfly key={c.key} look={l} pal={pal} />;
          return <HeartBuddy key={c.key} pal={pal} />;
        })}

        {/* twinkling sparkles */}
        {sparkles.length > 0 && (
          <G>
            <Twinkle cx={54} cy={70} r={5.4} delay={0} />
            <Twinkle cx={192} cy={112} r={4.2} delay={420} />
            <Twinkle cx={62} cy={188} r={6} delay={840} />
            <Twinkle cx={186} cy={40} r={3.6} delay={1260} />
          </G>
        )}
      </Svg>
    </Animated.View>
  );
}
