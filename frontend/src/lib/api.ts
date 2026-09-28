// Data access. Every call goes to the live API first and falls back to the bundled
// snapshot (public/snapshot*.json, regenerated daily from the same pipeline), so the
// demo never shows a blank screen. The UI always says which source it is showing.

import type { Advisory, FeedbackSummary, Forecast, Geo, Lang, Options, Validation } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TIMEOUT_MS = 8000;

export type Source = "live" | "snapshot";
export type Loaded<T> = { data: T; source: Source; error?: string };

async function getJSON<T>(url: string, timeoutMs = TIMEOUT_MS): Promise<T> {
  const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs), cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

type Snapshot = Forecast & { geo: Geo; validation: Validation; options: Options };
let snapshotPromise: Promise<Snapshot> | null = null;
function snapshot(): Promise<Snapshot> {
  snapshotPromise ??= getJSON<Snapshot>("/snapshot.json", 20000);
  return snapshotPromise;
}

async function withFallback<T>(live: () => Promise<T>, fromSnapshot: (s: Snapshot) => T): Promise<Loaded<T>> {
  try {
    return { data: await live(), source: "live" };
  } catch (e) {
    const error = e instanceof Error ? e.message : String(e);
    return { data: fromSnapshot(await snapshot()), source: "snapshot", error };
  }
}

export const loadForecast = () =>
  withFallback(() => getJSON<Forecast>(`${API_URL}/api/panchayats`), (s) => s);
export const loadGeo = () => withFallback(() => getJSON<Geo>(`${API_URL}/api/geo`), (s) => s.geo);
export const loadValidation = () =>
  withFallback(() => getJSON<Validation>(`${API_URL}/api/validation`), (s) => s.validation);
export const loadOptions = () => withFallback(() => getJSON<Options>(`${API_URL}/api/options`), (s) => s.options);

let advisoryCache: Promise<Record<string, Advisory>> | null = null;
export async function loadAdvisory(id: string, crop: string, stage: string, lang: Lang, preferSnapshot = false) {
  const q = new URLSearchParams({ panchayat_id: id, crop, stage, lang });
  const live = () => getJSON<Advisory>(`${API_URL}/api/advisory?${q}`);
  if (!preferSnapshot) {
    try {
      return { data: await live(), source: "live" as Source };
    } catch {
      /* fall through to the snapshot */
    }
  }
  advisoryCache ??= getJSON<Record<string, Advisory>>("/snapshot-advisories.json", 30000);
  const hit = (await advisoryCache)[`${id}|${crop}|${stage}|${lang}`];
  if (!hit) throw new Error("No advisory for this selection in the offline snapshot.");
  return { data: hit, source: "snapshot" as Source };
}

/** Alert codes for every panchayat (officer view). Falls back to the snapshot advisories. */
export async function loadAlerts(crop: string, stage: string, preferSnapshot = false): Promise<Loaded<Record<string, string[]>>> {
  if (!preferSnapshot) {
    try {
      const r = await getJSON<{ alerts: Record<string, string[]> }>(`${API_URL}/api/alerts?${new URLSearchParams({ crop, stage })}`);
      return { data: r.alerts, source: "live" };
    } catch {
      /* fall through */
    }
  }
  advisoryCache ??= getJSON<Record<string, Advisory>>("/snapshot-advisories.json", 30000);
  const all = await advisoryCache;
  const out: Record<string, string[]> = {};
  for (const [k, a] of Object.entries(all)) {
    const [id, c, s, lang] = k.split("|");
    if (c === crop && s === stage && lang === "en") out[id] = a.alerts;
  }
  return { data: out, source: "snapshot" };
}

export const audioUrl = (id: string, crop: string, stage: string, lang: Lang) =>
  `${API_URL}/api/advisory/audio?${new URLSearchParams({ panchayat_id: id, crop, stage, lang })}`;

export async function sendFeedback(body: {
  panchayat_id: string;
  date: string;
  variable: string;
  rating: "accurate" | "not_accurate";
  channel: string;
}) {
  const res = await fetch(`${API_URL}/api/feedback`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return (await res.json()) as { ok: boolean; total: number };
}

export const loadFeedbackSummary = () => getJSON<FeedbackSummary>(`${API_URL}/api/feedback/summary`);
