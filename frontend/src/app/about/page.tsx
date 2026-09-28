// How GramVarsha works: pipeline, data sources and honest limitations.
// Static page; the numbers it describes live on /validation.

import Link from "next/link";

type Step = { title: string; body: string; code: string };

const PIPELINE: Step[] = [
  {
    title: "Coarse block forecast",
    body: "One 5-day forecast for the whole block. Today: Open-Meteo GFS as an IMD proxy. The IMD block feed plugs into the same function.",
    code: "backend/forecast.py",
  },
  {
    title: "Kriging",
    body: "Ordinary kriging of each village's usual monthly difference from the block, fitted on training years only. Works for villages with no data.",
    code: "ml/kriging.py",
  },
  {
    title: "XGBoost correction",
    body: "Learns what kriging missed from terrain (elevation, slope, river distance, position), season and the day's block weather.",
    code: "ml/model.py",
  },
  {
    title: "SHAP explanation",
    body: "Every correction is split into named causes, marked as village-specific or block-wide, and written as a sentence.",
    code: "ml/explain.py",
  },
  {
    title: "Crop advisory",
    body: "Deterministic rules for 8 Sangli crops × 5 stages, hand-written in English, Hindi and Marathi. Optional LLM rewording may never change a number.",
    code: "backend/advisory.py",
  },
  {
    title: "SMS · WhatsApp · voice",
    body: "Reaches any phone. Nothing to install, nothing to type.",
    code: "backend/tts.py",
  },
  {
    title: "Farmer feedback",
    body: "Replies 1/2 and 👍/👎 are stored per panchayat and shown to officers. Real station data can replace the pseudo-truth for retraining.",
    code: "backend/db.py",
  },
];

const TIERS = [
  { t: "A", name: "Full ML", body: "Kriging + XGBoost, with confidence range and SHAP reasons." },
  { t: "B", name: "Physics only", body: "Models unavailable: lapse rate 6.5 °C/km and an orographic rain factor, no training needed." },
  { t: "C", name: "Pass-through", body: "No local data: the block value is shown unchanged and flagged “limited local data”." },
];

const SOURCES = [
  ["Block forecast (IMD proxy)", "Open-Meteo Forecast & Historical Forecast API, GFS 0.25°", "Free, no key"],
  ["Village “truth” for training", "Open-Meteo Archive API, ECMWF IFS ~9 km", "Pseudo ground truth"],
  ["Elevation, slope, aspect", "Copernicus GLO-90 DEM via Open-Meteo Elevation API", "90 m"],
  ["Villages, taluka boundary", "OpenStreetMap (Overpass), relation 9742028 / LGD 4302", "ODbL"],
  ["Krishna river", "OpenStreetMap (Nominatim), relation 337204", "ODbL"],
  ["Voice", "gTTS (Google Translate TTS), Marathi / Hindi / English", "Free"],
];

const LIMITS = [
  "The “truth” is a 9 km weather model, not rain gauges or AWS. Nearby villages can share one grid cell, which caps the village detail we can learn and prove. Real IMD AWS/ARG CSVs drop into data/imd_import/ and replace it.",
  "For daily max temperature and rainfall the gain over the block forecast is a better block-level forecast, not village-level detail. The Validation page shows this per variable.",
  "In the current models XGBoost leans on season and the day's block weather more than on terrain; most village-to-village detail comes from the kriging step. Miraj is flat (under 150 m of relief), so terrain signal is small.",
  "Scores cover day 0–1 lead time. Days 3–5 on the map are shown but not yet validated.",
  "Panchayat outlines are Voronoi cells around OSM village points, not official boundaries. LGD / Bhunaksha polygons replace them in production.",
  "Advisory thresholds are general agronomy rules of thumb and need review by the Sangli KVK / AMFU before farmers act on them.",
  "Marathi village names are hand-transliterated and marked for local checking.",
];

export default function AboutPage() {
  return (
    <main className="mx-auto w-full max-w-5xl space-y-12 px-4 py-8 sm:px-6">
      <header className="space-y-3">
        <p className="eyebrow">SIH26074 · Ministry of Earth Sciences · Team Hexadecimal, WCE Sangli</p>
        <h1 className="max-w-3xl text-2xl font-semibold leading-tight sm:text-3xl">
          From one block forecast to advice for every gram panchayat
        </h1>
        <p className="max-w-3xl text-muted">
          IMD issues agromet forecasts at block level, so every village in Miraj block gets the same numbers.
          GramVarsha estimates how each panchayat differs, says why, turns it into crop advice in the farmer&apos;s
          language, and learns from their replies.
        </p>
      </header>

      <section aria-labelledby="pipeline" className="space-y-4">
        <h2 id="pipeline" className="text-lg font-semibold">
          The pipeline
        </h2>
        <ol className="relative space-y-0">
          {PIPELINE.map((s, i) => (
            <li key={s.title} className="relative grid grid-cols-[2.25rem_minmax(0,1fr)] gap-3 pb-5 last:pb-0">
              {/* connector */}
              {i < PIPELINE.length - 1 && <span className="absolute left-[1.06rem] top-8 bottom-0 w-px bg-navy/25" aria-hidden />}
              <span
                className={`z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-semibold ${
                  i === 0 ? "border-amber bg-amber-soft text-ink" : "border-navy bg-card text-navy"
                }`}
              >
                {i + 1}
              </span>
              <div className="rounded-lg border border-line bg-card px-4 py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="font-semibold">{s.title}</h3>
                  <code className="num text-[11px] text-muted">{s.code}</code>
                </div>
                <p className="mt-1 text-sm text-muted">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="pl-12 text-sm text-muted">
          ↺ Feedback and any station data flow back into step 2 at the next retraining (<code className="num">make train</code>).
        </p>
      </section>

      <section aria-labelledby="tiers" className="space-y-4">
        <h2 id="tiers" className="text-lg font-semibold">
          It never fails silently
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {TIERS.map((t) => (
            <div key={t.t} className="rounded-lg border border-line bg-card p-4">
              <p className="flex items-center gap-2 font-semibold">
                <span className={`rounded px-2 py-0.5 text-xs ${t.t === "A" ? "bg-navy text-white" : "bg-amber text-ink"}`}>
                  Tier {t.t}
                </span>
                {t.name}
              </p>
              <p className="mt-2 text-sm text-muted">{t.body}</p>
            </div>
          ))}
        </div>
        <p className="text-sm text-muted">
          If the forecast source is down, the last good forecast is served with a &ldquo;stale since&rdquo; notice. If
          the server is down, the site falls back to a copy produced daily by the same pipeline, and says so.
        </p>
      </section>

      <section aria-labelledby="sources" className="space-y-4">
        <h2 id="sources" className="text-lg font-semibold">
          Open data, zero cost
        </h2>
        <div className="overflow-x-auto rounded-lg border border-line bg-card">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="bg-paper text-left text-xs text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Need</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Note</th>
              </tr>
            </thead>
            <tbody>
              {SOURCES.map(([a, b, c]) => (
                <tr key={a} className="border-t border-line">
                  <td className="px-3 py-2">{a}</td>
                  <td className="px-3 py-2 text-muted">{b}</td>
                  <td className="px-3 py-2 text-muted">{c}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="limits" className="space-y-3">
        <h2 id="limits" className="text-lg font-semibold">
          Limitations we know about
        </h2>
        <ul className="list-disc space-y-2 pl-5 text-sm text-muted">
          {LIMITS.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
        <p className="text-sm">
          The measured numbers are on{" "}
          <Link href="/validation" className="text-navy underline underline-offset-2">
            Validation
          </Link>
          .
        </p>
      </section>
    </main>
  );
}
