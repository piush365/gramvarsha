"use client";

// AMFU / KVK officer view: every panchayat in one sortable table, today's alert
// counts by type, farmer feedback, and a CSV export for the district bulletin.

import { useEffect, useMemo, useState } from "react";
import StatusBanner from "@/components/StatusBanner";
import { loadAlerts, loadFeedbackSummary, loadForecast, loadOptions, type Source } from "@/lib/api";
import { fmt, UNIT, VAR_LABEL } from "@/lib/scale";
import { VARS, type FeedbackSummary, type Forecast, type Options, type Var } from "@/lib/types";

type SortKey = "name" | "tier" | Var | `d_${Var}`;
const ALERT_LABEL: Record<string, string> = {
  HEAT: "Heat stress",
  HEAVY_RAIN: "Heavy rain: hold spraying",
  HARVEST_RAIN: "Rain at harvest",
  GRAPE_DOWNY: "Grape downy mildew",
  TURMERIC_DRAIN: "Turmeric drainage",
  POMEGRANATE_BLIGHT: "Pomegranate oily spot",
  WHEAT_HEAT: "Wheat heat stress",
  JOWAR_MOULD: "Jowar grain mould",
  FUNGAL: "Fungal risk at flowering",
  IRRIGATE: "Irrigate",
  SOWING_DRY: "Too dry to sow",
  WIND: "Wind: spray early only",
  NORMAL: "No weather risk",
};

export default function OfficerPage() {
  const [data, setData] = useState<{ f: Forecast; options: Options; source: Source } | null>(null);
  const [fb, setFb] = useState<FeedbackSummary | null>(null);
  const [fbError, setFbError] = useState(false);
  const [crop, setCrop] = useState("grapes");
  const [stage, setStage] = useState("flowering");
  const [alerts, setAlerts] = useState<Record<string, string[]> | null>(null);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "rain", desc: true });

  useEffect(() => {
    Promise.all([loadForecast(), loadOptions()]).then(([r, o]) => setData({ f: r.data, options: o.data, source: r.source }));
    loadFeedbackSummary().then(setFb).catch(() => setFbError(true));
  }, []);

  // Today's alerts for every panchayat for the chosen crop/stage (same rules engine as the SMS).
  useEffect(() => {
    if (!data) return;
    let live = true;
    loadAlerts(crop, stage, data.source === "snapshot")
      .then((r) => live && setAlerts(r.data))
      .catch(() => live && setAlerts({}));
    return () => {
      live = false;
    };
  }, [data, crop, stage]);

  const rows = useMemo(() => {
    if (!data) return [];
    const r = data.f.panchayats.map((p) => {
      const d = p.days[0].values;
      const row: Record<string, string | number> = { id: p.id, name: p.name, name_mr: p.name_mr, tier: p.tier };
      for (const v of VARS) {
        row[v] = d[v].value;
        row[`d_${v}`] = d[v].value - d[v].block;
      }
      return row;
    });
    const k = sort.key;
    return r.sort((a, b) => {
      const x = a[k];
      const y = b[k];
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return sort.desc ? -c : c;
    });
  }, [data, sort]);

  const alertCounts = useMemo(() => {
    const c: Record<string, number> = {};
    Object.values(alerts ?? {}).forEach((codes) => codes.forEach((code) => (c[code] = (c[code] ?? 0) + 1)));
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, [alerts]);

  if (!data)
    return (
      <main className="mx-auto w-full max-w-6xl space-y-3 px-4 py-6 sm:px-6">
        <div className="skeleton h-8 w-1/2" />
        <div className="skeleton h-96 w-full" />
      </main>
    );

  const { f } = data;
  const exportCsv = () => {
    const head = ["panchayat_id", "name", "tier", "date", ...VARS.flatMap((v) => [`${v}_block`, `${v}_gramvarsha`, `${v}_low`, `${v}_high`]), `alerts_${crop}_${stage}`];
    const lines = f.panchayats.flatMap((p) =>
      p.days.map((d) =>
        [
          p.id,
          p.name,
          p.tier,
          d.date,
          ...VARS.flatMap((v) => {
            const x = d.values[v];
            return [x.block, x.value, x.band?.[0] ?? "", x.band?.[1] ?? ""];
          }),
          d.lead === 0 ? (alerts?.[p.id] ?? []).join(" ") : "",
        ].join(","),
      ),
    );
    const blob = new Blob([[head.join(","), ...lines].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `gramvarsha_miraj_${f.dates[0]}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const th = (key: SortKey, label: React.ReactNode, right = true) => (
    <th className={`px-2 py-2 font-medium ${right ? "text-right" : "text-left"}`} aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"}>
      <button onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : true })} className="hover:text-ink">
        {label} {sort.key === key ? (sort.desc ? "↓" : "↑") : ""}
      </button>
    </th>
  );

  return (
    <>
      <StatusBanner source={data.source} generatedAt={f.generated_at} stale={f.stale} staleSince={f.stale_since} />
      <main className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">AMFU / KVK officer · Miraj block · {f.dates[0]}</p>
            <h1 className="text-2xl font-semibold">Today across {f.panchayats.length} panchayats</h1>
          </div>
          <button onClick={exportCsv} className="rounded bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy/90">
            Download 5-day CSV
          </button>
        </header>

        <div className="grid gap-4 lg:grid-cols-3">
          <section className="rounded-lg border border-line bg-card p-4 lg:col-span-2">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <h2 className="font-semibold">Alerts today for</h2>
              <select value={crop} onChange={(e) => setCrop(e.target.value)} className="rounded border border-line px-2 py-1 text-sm">
                {Object.entries(data.options.crops).map(([c, n]) => (
                  <option key={c} value={c}>
                    {n.en}
                  </option>
                ))}
              </select>
              <select value={stage} onChange={(e) => setStage(e.target.value)} className="rounded border border-line px-2 py-1 text-sm">
                {Object.entries(data.options.stages).map(([s, n]) => (
                  <option key={s} value={s}>
                    {n.en[0].toUpperCase() + n.en.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            {!alerts ? (
              <div className="skeleton h-24 w-full" />
            ) : (
              <ul className="grid gap-2 sm:grid-cols-2">
                {alertCounts.map(([code, n]) => (
                  <li key={code} className="flex items-center justify-between rounded border border-line px-3 py-2 text-sm">
                    <span>{ALERT_LABEL[code] ?? code}</span>
                    <span className="num font-semibold">
                      {n} <span className="font-normal text-muted">/ {f.panchayats.length}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-line bg-card p-4">
            <h2 className="mb-3 font-semibold">Farmer feedback</h2>
            {fbError ? (
              <p className="text-sm text-muted">Feedback needs the live server.</p>
            ) : !fb ? (
              <div className="skeleton h-24 w-full" />
            ) : fb.total === 0 ? (
              <p className="text-sm text-muted">No feedback yet. Use 👍/👎 on the map or reply 1/2 in the farmer view.</p>
            ) : (
              <div className="space-y-3 text-sm">
                <p>
                  <span className="num text-2xl font-semibold">{fb.accurate_pct}%</span>{" "}
                  <span className="text-muted">
                    said accurate ({fb.accurate} of {fb.total})
                  </span>
                </p>
                <ul className="space-y-1 text-xs text-muted">
                  {Object.entries(fb.by_channel).map(([ch, s]) => (
                    <li key={ch} className="flex justify-between">
                      <span className="uppercase">{ch}</span>
                      <span className="num">
                        👍 {s.accurate} · 👎 {s.not_accurate}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="text-[11px] text-muted">Stored in {fb.storage === "sqlite" ? "SQLite" : "Postgres"}.</p>
              </div>
            )}
          </section>
        </div>

        <section className="overflow-x-auto rounded-lg border border-line bg-card">
          <table className="w-full min-w-[880px] text-sm">
            <thead className="bg-paper text-xs text-muted">
              <tr>
                {th("name", "Panchayat", false)}
                {th("tier", "Tier", false)}
                {VARS.map((v) => th(v, <>{VAR_LABEL[v]} <span className="font-normal">{UNIT[v]}</span></>))}
                {th("d_tmin", "Δ Tmin vs block")}
                {th("d_rain", "Δ rain vs block")}
                <th className="px-2 py-2 text-left font-medium">Alerts ({crop}, {stage})</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id as string} className="border-t border-line hover:bg-paper">
                  <td className="px-2 py-1.5">
                    {r.name} <span className="font-[family-name:var(--font-mr)] text-muted">{r.name_mr}</span>
                  </td>
                  <td className="px-2 py-1.5">{r.tier}</td>
                  {VARS.map((v) => (
                    <td key={v} className="num px-2 py-1.5 text-right">
                      {fmt(v, r[v] as number)}
                    </td>
                  ))}
                  <td className="num px-2 py-1.5 text-right text-muted">{(r.d_tmin as number).toFixed(1)}</td>
                  <td className="num px-2 py-1.5 text-right text-muted">{(r.d_rain as number).toFixed(1)}</td>
                  <td className="px-2 py-1.5 text-xs">
                    {(alerts?.[r.id as string] ?? []).map((c) => ALERT_LABEL[c] ?? c).join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </>
  );
}
