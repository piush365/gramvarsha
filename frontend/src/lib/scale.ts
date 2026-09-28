// Colour scales for the map and the spread strip. One sequential ramp per variable,
// built from the brand palette. The domain covers BOTH block and downscaled values,
// so toggling modes never rescales: the uniform block colour and the downscaled
// spread are read against the same legend.

import type { Forecast, Var } from "./types";

const RAMPS: Record<Var, string[]> = {
  rain: ["#F3F6F8", "#9FB6CB", "#1B3A5C"],
  tmax: ["#FBF1DC", "#E3A33B", "#8A4B12"],
  tmin: ["#FBF1DC", "#E3A33B", "#8A4B12"],
  rh: ["#EEF4EA", "#8FB983", "#2F5A27"],
  wind: ["#F1F2F4", "#8A97A8", "#1B3A5C"],
};

export const VAR_LABEL: Record<Var, string> = {
  rain: "Rain",
  tmax: "Max temp",
  tmin: "Min temp",
  rh: "Humidity",
  wind: "Wind",
};

export const UNIT: Record<Var, string> = { rain: "mm", tmax: "°C", tmin: "°C", rh: "%", wind: "km/h" };

const hex = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const lerp = (a: number, b: number, t: number) => Math.round(a + (b - a) * t);

export function colour(v: Var, t: number): string {
  const stops = RAMPS[v].map(hex);
  const x = Math.min(1, Math.max(0, t)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const f = x - i;
  const [r, g, b] = stops[i].map((c, k) => lerp(c, stops[i + 1][k], f));
  return `rgb(${r} ${g} ${b})`;
}

export type Domain = { min: number; max: number };

export function domainFor(data: Forecast, v: Var, day: number): Domain {
  const vals = data.panchayats.flatMap((p) => [p.days[day].values[v].value, p.days[day].values[v].block]);
  let min = Math.min(...vals);
  let max = Math.max(...vals);
  const minWidth = v === "rain" ? 2 : v === "rh" ? 4 : 1; // avoid exaggerating tiny differences
  if (max - min < minWidth) {
    const mid = (max + min) / 2;
    min = mid - minWidth / 2;
    max = mid + minWidth / 2;
  }
  if (v === "rain") min = Math.max(0, min);
  return { min, max };
}

export const norm = (d: Domain, x: number) => (d.max === d.min ? 0.5 : (x - d.min) / (d.max - d.min));

export function fmt(v: Var, x: number): string {
  return v === "rh" ? `${Math.round(x)}` : x.toFixed(1);
}

export function fmtDay(date: string, lead: number): string {
  if (lead === 0) return "Today";
  if (lead === 1) return "Tomorrow";
  return new Date(date + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric" });
}
