"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import PanchayatPanel from "@/components/PanchayatPanel";
import SpreadStrip from "@/components/SpreadStrip";
import StatusBanner from "@/components/StatusBanner";
import { loadForecast, loadGeo, loadOptions, loadValidation, type Source } from "@/lib/api";
import { domainFor, fmtDay, UNIT, VAR_LABEL } from "@/lib/scale";
import { VARS, type Forecast, type Geo, type Options, type Validation, type Var } from "@/lib/types";

const ForecastMap = dynamic(() => import("@/components/ForecastMap"), {
  ssr: false,
  loading: () => <div className="skeleton h-full w-full" />,
});

type Loaded = { forecast: Forecast; geo: Geo; options: Options; validation: Validation | null; source: Source };

export default function Dashboard() {
  const [data, setData] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [variable, setVariable] = useState<Var>("rain");
  const [day, setDay] = useState(0);
  const [mode, setMode] = useState<"block" | "downscaled">("downscaled");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    // Deep links for demos, e.g. /?mode=block&var=tmin&day=1&p=mhaisal
    const q = new URLSearchParams(window.location.search);
    const wanted = q.get("p");
    Promise.all([loadForecast(), loadGeo(), loadOptions(), loadValidation().catch(() => null)])
      .then(([f, g, o, v]) => {
        setData({
          forecast: f.data,
          geo: g.data,
          options: o.data,
          validation: v?.data ?? null,
          source: f.source === "live" && g.source === "live" ? "live" : "snapshot",
        });
        // Start on the panchayat furthest from the block value: the most telling example.
        const ps = f.data.panchayats;
        const far = [...ps].sort(
          (a, b) =>
            Math.abs(b.days[0].values.rain.value - b.days[0].values.rain.block) -
            Math.abs(a.days[0].values.rain.value - a.days[0].values.rain.block),
        )[0];
        setSelectedId(ps.some((p) => p.id === wanted) ? wanted : (far?.id ?? null));
        const m = q.get("mode");
        if (m === "block" || m === "downscaled") setMode(m);
        const qv = q.get("var");
        if (qv && (VARS as readonly string[]).includes(qv)) setVariable(qv as Var);
        const d = Number(q.get("day"));
        if (d >= 1 && d < f.data.dates.length) setDay(d);
      })
      .catch((e) => setFailed(String(e?.message ?? e)));
  }, []);

  const domain = useMemo(() => (data ? domainFor(data.forecast, variable, day) : null), [data, variable, day]);

  if (failed) return <ErrorState message={failed} />;
  if (!data || !domain) return <DashboardSkeleton />;

  const { forecast } = data;
  const selected = forecast.panchayats.find((p) => p.id === selectedId) ?? null;
  const spread = forecast.spread[day];

  return (
    <>
      <StatusBanner
        source={data.source}
        generatedAt={forecast.generated_at}
        stale={forecast.stale}
        staleSince={forecast.stale_since}
      />
      <main className="grid flex-1 grid-cols-[minmax(0,1fr)] gap-0 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="flex min-w-0 flex-col">
          {/* Headline + controls */}
          <section className="space-y-3 border-b border-line bg-card px-4 py-3 sm:px-6">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="eyebrow">
                  {forecast.panchayats.length} gram panchayats · Miraj block · {fmtDay(forecast.dates[day], day)}
                </p>
                <h1 className="text-lg font-semibold leading-snug sm:text-xl">
                  One block forecast, {forecast.panchayats.length} different villages.{" "}
                  <span className="font-normal text-muted">
                    Spread today:{" "}
                    <span className="num text-ink">
                      {spread.rain} mm
                    </span>{" "}
                    rain ·{" "}
                    <span className="num text-ink">
                      {spread.tmax} °C
                    </span>{" "}
                    max temp.
                  </span>
                </h1>
              </div>
              <ModeToggle mode={mode} onChange={setMode} />
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <Segmented
                label="Variable"
                items={VARS.map((v) => ({ key: v, label: VAR_LABEL[v] }))}
                value={variable}
                onChange={(v) => setVariable(v as Var)}
              />
              <Segmented
                label="Day"
                items={forecast.dates.map((d, i) => ({ key: String(i), label: fmtDay(d, i) }))}
                value={String(day)}
                onChange={(v) => setDay(Number(v))}
              />
            </div>
          </section>

          {/* Spread strip = legend */}
          <section className="border-b border-line bg-card px-4 pb-1 pt-2 sm:px-6">
            <div className="flex items-baseline justify-between text-xs text-muted">
              <span>
                {mode === "block"
                  ? "Block forecast: every panchayat gets the same value."
                  : "GramVarsha: each dot is one panchayat."}
              </span>
              <span className="num">{UNIT[variable]}</span>
            </div>
            <SpreadStrip
              panchayats={forecast.panchayats}
              variable={variable}
              day={day}
              mode={mode}
              domain={domain}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </section>

          {/* Map */}
          <section className="relative h-[58vh] min-h-[380px] lg:h-auto lg:flex-1">
            <ForecastMap
              geo={data.geo}
              block={forecast.block}
              panchayats={forecast.panchayats}
              variable={variable}
              day={day}
              mode={mode}
              domain={domain}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
            <p className="pointer-events-none absolute bottom-6 left-2 z-[500] hidden max-w-[18rem] rounded bg-card/90 px-2 py-1 text-[11px] leading-snug text-muted shadow-sm sm:block">
              Panchayat outlines are approximate (Voronoi around village points); LGD boundaries in production. Badge =
              tier A/B/C.
            </p>
          </section>
          <p className="border-t border-line bg-card px-4 py-2 text-[11px] text-muted sm:hidden">
            Panchayat outlines are approximate (Voronoi around village points); LGD boundaries in production. Badge =
            tier A/B/C.
          </p>
        </div>

        <aside className="min-w-0 border-l border-line bg-card lg:max-h-[calc(100vh-49px)] lg:overflow-y-auto">
          {selected ? (
            <PanchayatPanel
              p={selected}
              day={day}
              variable={variable}
              onVariable={setVariable}
              options={data.options}
              validation={data.validation}
              source={data.source}
            />
          ) : (
            <p className="p-6 text-sm text-muted">Select a panchayat on the map to see its forecast and advisory.</p>
          )}
        </aside>
      </main>
    </>
  );
}

function ModeToggle({ mode, onChange }: { mode: "block" | "downscaled"; onChange: (m: "block" | "downscaled") => void }) {
  const opt = (m: "block" | "downscaled", label: string) => (
    <button
      role="radio"
      aria-checked={mode === m}
      onClick={() => onChange(m)}
      className={`px-4 py-2 text-sm font-medium transition-colors ${
        mode === m ? (m === "block" ? "bg-amber text-ink" : "bg-navy text-white") : "bg-card text-muted hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div role="radiogroup" aria-label="Forecast shown" className="flex overflow-hidden rounded-full border border-navy/30">
      {opt("block", "Block forecast")}
      {opt("downscaled", "GramVarsha downscaled")}
    </div>
  );
}

function Segmented({
  label,
  items,
  value,
  onChange,
}: {
  label: string;
  items: { key: string; label: string }[];
  value: string;
  onChange: (k: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="eyebrow">{label}</span>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1">
        {items.map((it) => (
          <button
            key={it.key}
            role="radio"
            aria-checked={value === it.key}
            onClick={() => onChange(it.key)}
            className={`rounded px-2.5 py-1 text-sm ${
              value === it.key ? "bg-navy text-white" : "bg-paper text-ink hover:bg-navy-soft"
            }`}
          >
            {it.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <main className="grid flex-1 lg:grid-cols-[minmax(0,1fr)_420px]" aria-busy="true" aria-label="Loading forecast">
      <div className="space-y-3 p-4 sm:p-6">
        <div className="skeleton h-4 w-64" />
        <div className="skeleton h-7 w-3/4" />
        <div className="skeleton h-8 w-full" />
        <div className="skeleton h-16 w-full" />
        <div className="skeleton h-[50vh] w-full" />
      </div>
      <div className="space-y-3 border-l border-line p-4">
        <div className="skeleton h-6 w-40" />
        <div className="skeleton h-40 w-full" />
        <div className="skeleton h-32 w-full" />
      </div>
    </main>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <main className="mx-auto max-w-lg flex-1 p-8">
      <h1 className="text-xl font-semibold">The forecast could not be loaded</h1>
      <p className="mt-2 text-sm text-muted">
        Neither the live server nor the offline copy responded ({message}). Check the network connection and reload
        the page.
      </p>
      <button onClick={() => location.reload()} className="mt-4 rounded bg-navy px-4 py-2 text-sm text-white">
        Reload
      </button>
    </main>
  );
}
