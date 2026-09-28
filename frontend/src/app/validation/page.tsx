"use client";

// Honest validation: every number comes from ml/metrics.json (ml/evaluate.py),
// scored on the last 3 months, which no model saw during training.

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { loadGeo, loadValidation, type Source } from "@/lib/api";
import { DIVERGING, improvementColour, UNIT, VAR_LABEL } from "@/lib/scale";
import { VARS, type Geo, type Method, type Validation, type Var } from "@/lib/types";

const ErrorMap = dynamic(() => import("@/components/ErrorMap"), {
  ssr: false,
  loading: () => <div className="skeleton h-full w-full" />,
});

// Validated categorical palette (scripts/validate_palette.js: all checks pass; amber and
// light blue are below 3:1 on white, so every bar also carries a direct value label).
const SERIES: { key: Method; label: string; colour: string }[] = [
  { key: "block", label: "Raw block forecast", colour: "#E3A33B" },
  { key: "bias", label: "Block + bias correction", colour: "#5A8F4E" },
  { key: "krig", label: "Kriging only", colour: "#5B9BD5" },
  { key: "final", label: "GramVarsha (kriging + XGBoost)", colour: "#1F5AAE" },
];
type Holdout = "spatial" | "temporal";

export default function ValidationPage() {
  const [v, setV] = useState<Validation | null>(null);
  const [geo, setGeo] = useState<Geo | null>(null);
  const [source, setSource] = useState<Source>("live");
  const [holdout, setHoldout] = useState<Holdout>("spatial");
  const [mapVar, setMapVar] = useState<Var>("tmin");

  useEffect(() => {
    loadValidation().then((r) => {
      setV(r.data);
      setSource(r.source);
    });
    loadGeo().then((r) => setGeo(r.data));
  }, []);

  if (!v)
    return (
      <main className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6 sm:px-6">
        <div className="skeleton h-8 w-2/3" />
        <div className="skeleton h-64 w-full" />
      </main>
    );

  const tab = v[holdout];
  const pv = v.per_village_temporal_rmse;
  const pcts = Object.values(pv).map((r) => 100 * (1 - r[mapVar].final / r[mapVar].block));
  const maxAbs = Math.max(5, ...pcts.map(Math.abs));
  const better = pcts.filter((x) => x > 0).length;
  // Headline is computed from the verdicts, never typed in.
  const nBeat = VARS.filter((k) => v.verdict[k].beats_block).length;
  const nVillage = VARS.filter((k) => v.verdict[k].resolves_village_differences).length;
  const WORDS = ["none", "one", "two", "three", "four", "all five"];
  const terrainInTop = VARS.reduce(
    (n, k) => n + Object.keys(v.feature_importance[k]).slice(0, 6).filter((f) => TERRAIN.has(f)).length,
    0,
  );

  return (
    <main className="mx-auto w-full max-w-6xl space-y-10 px-4 py-6 sm:px-6">
      <header className="space-y-3">
        <p className="eyebrow">
          Validation · {v.test_period.start} to {v.test_period.end} · {v.test_period.days} held-out days
          {source === "snapshot" && " · offline copy"}
        </p>
        <h1 className="max-w-3xl text-2xl font-semibold leading-tight sm:text-3xl">
          Does downscaling beat the block forecast? For {nBeat === 5 ? "all five" : `${WORDS[nBeat]} of five`}{" "}
          variables, yes. For telling villages apart, {nVillage === 5 ? "all five" : `${WORDS[nVillage]} of five`}.
        </h1>
        <p className="max-w-3xl text-muted">
          Errors are measured on the 2026 monsoon months, which no model saw during training. The first chart uses
          villages the model has also never seen, the realistic case for a panchayat with no weather station.
        </p>
      </header>

      {/* RMSE small multiples */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Forecast error by method (RMSE, lower is better)</h2>
          <div role="radiogroup" aria-label="Holdout" className="flex overflow-hidden rounded border border-line text-sm">
            {(
              [
                ["spatial", "Unseen villages"],
                ["temporal", "All villages"],
              ] as [Holdout, string][]
            ).map(([k, label]) => (
              <button
                key={k}
                role="radio"
                aria-checked={holdout === k}
                onClick={() => setHoldout(k)}
                className={`px-3 py-1.5 ${holdout === k ? "bg-navy text-white" : "bg-card hover:bg-navy-soft"}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <Legend />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {VARS.map((k) => (
            <Bars key={k} variable={k} scores={SERIES.map((s) => ({ ...s, value: tab[k][s.key].rmse }))} />
          ))}
        </div>
        <p className="text-xs text-muted">
          {holdout === "spatial"
            ? "Unseen villages: 5-fold cross-validation over villages; each fold's kriging and XGBoost are fitted without those villages."
            : "All villages: the production model, trained on every village before June 2026."}{" "}
          Bias correction removes only the block forecast&apos;s average error for the month, so the gap between green
          and blue is what the terrain model adds.
        </p>
      </section>

      {/* Verdict table */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Village-to-village differences (unseen villages)</h2>
        <p className="max-w-3xl text-sm text-muted">
          RMSE of each village&apos;s difference from the day&apos;s village average. The block forecast gives every
          village the same value, so its error equals the true spread. A method only &ldquo;resolves villages&rdquo;
          if it cuts that error by more than 10&nbsp;%.
        </p>
        <div className="overflow-x-auto rounded-lg border border-line bg-card">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-paper text-left text-xs text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Variable</th>
                <th className="px-3 py-2 text-right font-medium">True spread (SD)</th>
                <th className="px-3 py-2 text-right font-medium">Block error</th>
                <th className="px-3 py-2 text-right font-medium">GramVarsha error</th>
                <th className="px-3 py-2 font-medium">Beats block</th>
                <th className="px-3 py-2 font-medium">Beats bias correction</th>
                <th className="px-3 py-2 font-medium">Resolves villages</th>
              </tr>
            </thead>
            <tbody>
              {VARS.map((k) => {
                const s = v.spatial[k];
                const vd = v.verdict[k];
                return (
                  <tr key={k} className="border-t border-line">
                    <td className="px-3 py-2">
                      {VAR_LABEL[k]} <span className="text-xs text-muted">{UNIT[k]}</span>
                    </td>
                    <td className="num px-3 py-2 text-right">{s.truth_spread_sd.toFixed(2)}</td>
                    <td className="num px-3 py-2 text-right">{s.spatial_pattern_rmse.block.toFixed(2)}</td>
                    <td className="num px-3 py-2 text-right">{s.spatial_pattern_rmse.final.toFixed(2)}</td>
                    <Verdict ok={vd.beats_block} />
                    <Verdict ok={vd.beats_bias_corrected} />
                    <Verdict ok={vd.resolves_village_differences} />
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Per-panchayat map */}
      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="h-[420px] overflow-hidden rounded-lg border border-line">
          {geo ? <ErrorMap geo={geo} validation={v} variable={mapVar} maxAbs={maxAbs} /> : <div className="skeleton h-full" />}
        </div>
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Error change in each panchayat</h2>
          <p className="text-sm text-muted">
            RMSE of GramVarsha vs the raw block forecast in every panchayat over the held-out months. {better} of{" "}
            {pcts.length} panchayats improve for {VAR_LABEL[mapVar].toLowerCase()}.
          </p>
          <div className="flex flex-wrap gap-1">
            {VARS.map((k) => (
              <button
                key={k}
                onClick={() => setMapVar(k)}
                aria-pressed={mapVar === k}
                className={`rounded px-2.5 py-1 text-sm ${mapVar === k ? "bg-navy text-white" : "bg-card hover:bg-navy-soft"}`}
              >
                {VAR_LABEL[k]}
              </button>
            ))}
          </div>
          <div>
            <div
              className="h-2.5 rounded"
              style={{
                background: `linear-gradient(90deg, ${improvementColour(-maxAbs, maxAbs)}, ${DIVERGING.mid}, ${improvementColour(maxAbs, maxAbs)})`,
              }}
            />
            <div className="num mt-1 flex justify-between text-[11px] text-muted">
              <span>{maxAbs.toFixed(0)}% worse</span>
              <span>same</span>
              <span>{maxAbs.toFixed(0)}% better</span>
            </div>
          </div>
        </div>
      </section>

      {/* Feature importance */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">What the XGBoost step relies on</h2>
        <p className="max-w-3xl text-sm text-muted">
          Mean absolute SHAP value per feature on the held-out months (top 6). Green = terrain (can explain village
          differences), blue = season and block weather (corrects the forecast for the whole block).{" "}
          {terrainInTop === 0
            ? "No terrain feature ranks in the top 6 for any variable: XGBoost mainly corrects the coarse forecast day by day, and the village-to-village pattern comes from the kriging step."
            : `${terrainInTop} of the ${VARS.length * 6} top-6 slots are terrain features.`}
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {VARS.map((k) => (
            <Importance key={k} variable={k} values={v.feature_importance[k]} />
          ))}
        </div>
      </section>

      {/* Data honesty */}
      <section className="space-y-2 rounded-lg border border-line bg-card p-4">
        <h2 className="text-lg font-semibold">About this data</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          {v.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
          <li>
            Nothing was tuned on the held-out months. Model settings are fixed in code; early stopping and the
            kriging-or-XGBoost choice use separate validation weeks.
          </li>
        </ul>
      </section>
    </main>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
      {SERIES.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <i className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.colour }} />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

function Bars({ variable, scores }: { variable: Var; scores: { key: string; label: string; colour: string; value: number }[] }) {
  const max = Math.max(...scores.map((s) => s.value));
  const block = scores[0].value;
  const final = scores[scores.length - 1].value;
  const gain = 100 * (1 - final / block);
  return (
    <figure className="rounded-lg border border-line bg-card p-3">
      <figcaption className="flex items-baseline justify-between">
        <span className="font-medium">{VAR_LABEL[variable]}</span>
        <span className="text-xs text-muted">{UNIT[variable]}</span>
      </figcaption>
      <p className={`num text-xs ${gain > 0 ? "text-[#1F5AAE]" : "text-danger"}`}>
        {gain > 0 ? "−" : "+"}
        {Math.abs(gain).toFixed(0)}% error vs block
      </p>
      <div className="mt-3 space-y-1.5">
        {scores.map((s) => (
          <div key={s.key} className="group flex items-center gap-2" title={`${s.label}: ${s.value.toFixed(2)} ${UNIT[variable]}`}>
            <div className="h-4 flex-1">
              <div
                className="h-full rounded-r-[4px] transition-opacity group-hover:opacity-80"
                style={{ width: `${(s.value / max) * 100}%`, background: s.colour }}
              />
            </div>
            <span className="num w-10 text-right text-xs">{s.value.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </figure>
  );
}

const FEATURE_NAMES: Record<string, string> = {
  elevation_m: "elevation",
  elev_diff_m: "height vs block centre",
  slope_deg: "slope",
  aspect_sin: "slope direction E/W",
  aspect_cos: "slope direction N/S",
  tpi_m: "hill/hollow position",
  dist_river_km: "distance to river",
  dx_km: "east-west position",
  dy_km: "north-south position",
  doy_sin: "season (sin)",
  doy_cos: "season (cos)",
  block_tmax: "block max temp",
  block_tmin: "block min temp",
  block_rain: "block rain",
  block_rh: "block humidity",
  block_wind: "block wind",
};
const TERRAIN = new Set(["elevation_m", "elev_diff_m", "slope_deg", "aspect_sin", "aspect_cos", "tpi_m", "dist_river_km", "dx_km", "dy_km"]);

function Importance({ variable, values }: { variable: Var; values: Record<string, number> }) {
  const top = Object.entries(values).slice(0, 6);
  const max = Math.max(...top.map(([, x]) => x));
  return (
    <figure className="rounded-lg border border-line bg-card p-3">
      <figcaption className="mb-2 font-medium">{VAR_LABEL[variable]}</figcaption>
      <div className="space-y-1">
        {top.map(([f, x]) => (
          <div key={f} className="text-xs" title={`${FEATURE_NAMES[f] ?? f}: ${x.toFixed(3)}`}>
            <div className="flex justify-between text-muted">
              <span>{FEATURE_NAMES[f] ?? f}</span>
              <span className="num">{x.toFixed(3)}</span>
            </div>
            <div className="h-1.5 rounded-r-[4px] bg-paper">
              <div className={`h-full rounded-r-[4px] ${TERRAIN.has(f) ? "bg-forest" : "bg-navy/70"}`} style={{ width: `${(x / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-muted">
        <span className="text-forest">■</span> terrain <span className="ml-2 text-navy/70">■</span> block weather / season
      </p>
    </figure>
  );
}

function Verdict({ ok }: { ok: boolean }) {
  return (
    <td className="px-3 py-2">
      <span className={`inline-flex items-center gap-1 text-xs font-medium ${ok ? "text-forest" : "text-danger"}`}>
        <span aria-hidden>{ok ? "✓" : "✕"}</span> {ok ? "Yes" : "No"}
      </span>
    </td>
  );
}
