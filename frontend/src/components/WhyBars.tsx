// Horizontal bars of the SHAP-style contributions behind one correction.
// Green = village-specific (terrain, position, kriged local pattern).
// Navy  = block-wide (season, today's block weather, the coarse model's usual bias).

import type { Explanation } from "@/lib/types";

export default function WhyBars({ ex }: { ex: Explanation }) {
  const max = Math.max(0.01, ...ex.parts.map((p) => Math.abs(p.value)));
  const fmt = (v: number) => `${v > 0 ? "+" : ""}${ex.unit === "%" ? Math.round(v) : v.toFixed(1)}`;
  return (
    <div className="space-y-1.5">
      {ex.parts.map((p) => {
        const w = (Math.abs(p.value) / max) * 34; // max 34 % of the track, leaving room for the number
        return (
          <div key={p.label} className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] items-center gap-3 text-xs">
            <span className="leading-tight text-muted">
              {p.label}
            </span>
            <div className="relative h-4">
              <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
              <div
                className={`absolute inset-y-0.5 rounded-sm ${p.kind === "local" ? "bg-forest" : "bg-navy/70"}`}
                style={p.value >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
              />
              <span
                className="num absolute top-1/2 -translate-y-1/2 text-[11px] text-ink"
                style={p.value >= 0 ? { right: 0 } : { left: 0 }}
              >
                {fmt(p.value)}
              </span>
            </div>
          </div>
        );
      })}
      <div className="flex gap-4 pt-1 text-[11px] text-muted">
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-sm bg-forest" /> this village
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-sm bg-navy/70" /> whole block
        </span>
      </div>
    </div>
  );
}
