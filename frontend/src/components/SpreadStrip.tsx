"use client";

// One dot per panchayat on a value axis. In block mode all dots sit on the single
// block value; in downscaled mode they spread to their own values. Same axis and
// colours as the map legend, so the strip doubles as the legend.

import { useLayoutEffect, useRef, useState } from "react";
import { colour, fmt, norm, UNIT, type Domain } from "@/lib/scale";
import type { Panchayat, Var } from "@/lib/types";

type Props = {
  panchayats: Panchayat[];
  variable: Var;
  day: number;
  mode: "block" | "downscaled";
  domain: Domain;
  selectedId: string | null;
  onSelect: (id: string) => void;
};

const H = 64;
const PAD = 14;
const ROWS = 4;

export default function SpreadStrip({ panchayats, variable, day, mode, domain, selectedId, onSelect }: Props) {
  // Draw in real pixels (not a scaled viewBox) so dots and labels stay legible on phones.
  const box = useRef<HTMLElement>(null);
  const [W, setW] = useState(0); // 0 until measured: nothing is drawn wider than the screen
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(Math.max(260, Math.round(el.clientWidth))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const x = (v: number) => PAD + norm(domain, v) * (W - 2 * PAD);
  const blockVal = panchayats[0]?.days[day].values[variable].block ?? 0;
  // Stable vertical jitter so overlapping dots stay visible (sorted by value, cycled across rows).
  const order = [...panchayats]
    .sort((a, b) => a.days[day].values[variable].value - b.days[day].values[variable].value)
    .map((p) => p.id);
  const row = new Map(order.map((id, i) => [id, i % ROWS]));
  const ticks = W < 500 ? 3 : 5;

  return (
    <figure ref={box} className="min-h-[86px] w-full overflow-hidden" aria-label={`${panchayats.length} panchayats on a ${UNIT[variable]} scale`}>
      {W > 0 && <svg width={W} height={H + 22} className="block" role="img">
        <defs>
          <linearGradient id="gv-ramp" x1="0" x2="1">
            {Array.from({ length: 11 }, (_, i) => (
              <stop key={i} offset={`${i * 10}%`} stopColor={colour(variable, i / 10)} />
            ))}
          </linearGradient>
        </defs>
        <rect x={PAD} y={H - 6} width={W - 2 * PAD} height={6} rx={3} fill="url(#gv-ramp)" />
        {Array.from({ length: ticks }, (_, i) => {
          const v = domain.min + ((domain.max - domain.min) * i) / (ticks - 1);
          return (
            <text key={i} x={x(v)} y={H + 16} textAnchor="middle" className="num" fontSize="12" fill="#5b6875">
              {fmt(variable, v)}
            </text>
          );
        })}
        {/* The block value: one amber tick */}
        <line x1={x(blockVal)} x2={x(blockVal)} y1={2} y2={H} stroke="#E3A33B" strokeWidth={2} strokeDasharray="4 3" />
        <text
          x={x(blockVal) + (norm(domain, blockVal) > 0.7 ? -6 : 6)}
          y={11}
          textAnchor={norm(domain, blockVal) > 0.7 ? "end" : "start"}
          fontSize="11"
          fill="#8a5a10"
          className="num"
        >
          block {fmt(variable, blockVal)}
        </text>
        {panchayats.map((p) => {
          const v = p.days[day].values[variable];
          const val = mode === "block" ? v.block : v.value;
          const cy = 18 + (row.get(p.id) ?? 0) * 9;
          const sel = p.id === selectedId;
          return (
            <circle
              key={p.id}
              className="gv-dot cursor-pointer"
              cx={0}
              cy={cy}
              r={sel ? 7 : 5}
              style={{ transform: `translateX(${x(val)}px)` }}
              fill={colour(variable, norm(domain, val))}
              stroke={sel ? "#1B3A5C" : "#ffffff"}
              strokeWidth={sel ? 2.5 : 1.2}
              onClick={() => onSelect(p.id)}
            >
              <title>{`${p.name}: ${fmt(variable, val)} ${UNIT[variable]}`}</title>
            </circle>
          );
        })}
      </svg>}
    </figure>
  );
}
