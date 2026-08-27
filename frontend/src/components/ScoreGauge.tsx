"use client";

import { useEffect, useRef, useState } from "react";
import { BAND_HEX, BAND_META } from "@/lib/utils";
import type { RiskBand } from "@/lib/types";

const MIN = 300;
const MAX = 850;
const START_ANGLE = 170; // degrees
const SWEEP = 200;

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const a = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function arcPath(cx: number, cy: number, r: number, a0: number, a1: number) {
  const p0 = polar(cx, cy, r, a0);
  const p1 = polar(cx, cy, r, a1);
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
  return `M ${p0.x} ${p0.y} A ${r} ${r} 0 ${large} 1 ${p1.x} ${p1.y}`;
}

/** Deliberately quiet: a 200° arc, no needle, no ticks, no glow, no gradient. */
export function ScoreGauge({
  score,
  band,
  size = "lg",
  animate = false,
}: {
  score: number;
  band: RiskBand;
  size?: "sm" | "lg";
  animate?: boolean;
}) {
  const dim = size === "lg" ? 220 : 28;
  const stroke = size === "lg" ? 8 : 3;
  const r = (dim - stroke) / 2 - (size === "lg" ? 6 : 1);
  const cx = dim / 2;
  const cy = size === "lg" ? dim / 2 + 8 : dim / 2;
  const frac = Math.min(1, Math.max(0, (score - MIN) / (MAX - MIN)));
  const endAngle = START_ANGLE + SWEEP * frac;
  const hex = BAND_HEX[band];

  const [shown, setShown] = useState(animate && size === "lg" ? MIN : score);
  const raf = useRef<number>();
  useEffect(() => {
    if (!animate || size !== "lg") {
      setShown(score);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setShown(score);
      return;
    }
    const t0 = performance.now();
    const dur = 900;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(Math.round(MIN + (score - MIN) * eased));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [score, animate, size]);

  if (size === "sm") {
    return (
      <svg width={dim} height={dim} viewBox={`0 0 ${dim} ${dim}`} role="img" aria-label={`Score ${score}`}>
        <path d={arcPath(cx, cy, r, START_ANGLE, START_ANGLE + SWEEP)} fill="none" stroke="var(--rule)" strokeWidth={stroke} strokeLinecap="round" />
        <path d={arcPath(cx, cy, r, START_ANGLE, Math.max(START_ANGLE + 0.5, endAngle))} fill="none" stroke={hex} strokeWidth={stroke} strokeLinecap="round" />
      </svg>
    );
  }

  return (
    <div className="flex flex-col items-center" role="img" aria-label={`Credit score ${score} of 850, ${BAND_META[band].label.toLowerCase()}`}>
      <svg width={dim} height={dim - 24} viewBox={`0 0 ${dim} ${dim - 8}`}>
        <path d={arcPath(cx, cy, r, START_ANGLE, START_ANGLE + SWEEP)} fill="none" stroke="var(--rule)" strokeWidth={stroke} strokeLinecap="round" />
        <path d={arcPath(cx, cy, r, START_ANGLE, Math.max(START_ANGLE + 0.5, endAngle))} fill="none" stroke={hex} strokeWidth={stroke} strokeLinecap="round" />
        <text x={polar(cx, cy, r, START_ANGLE).x} y={polar(cx, cy, r, START_ANGLE).y + 18} textAnchor="middle" className="fill-ink-faint" style={{ fontSize: 11, fontFamily: "var(--font-plex-mono)" }}>300</text>
        <text x={polar(cx, cy, r, START_ANGLE + SWEEP).x} y={polar(cx, cy, r, START_ANGLE + SWEEP).y + 18} textAnchor="middle" className="fill-ink-faint" style={{ fontSize: 11, fontFamily: "var(--font-plex-mono)" }}>850</text>
      </svg>
      <div className="-mt-10 flex flex-col items-center">
        <span className="font-mono text-score-hero tabular-nums" style={{ color: hex }}>{shown}</span>
        <span className="mt-1 text-label uppercase text-ink-muted">{BAND_META[band].label}</span>
      </div>
    </div>
  );
}
