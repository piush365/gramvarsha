"use client";

import { useMemo, useState } from "react";
import { CorrectedForecast, BlockForecast } from "@/lib/downscale";
import { generateAdvisory, CROPS, STAGES, Crop, CropStage, Lang } from "@/lib/advisory";

export default function ForecastPanel({
  gpName,
  elevationM,
  block,
  corrected,
}: {
  gpName: string;
  elevationM: number;
  block: BlockForecast;
  corrected: CorrectedForecast;
}) {
  const [crop, setCrop] = useState<Crop>("sugarcane");
  const [stage, setStage] = useState<CropStage>("flowering");
  const [lang, setLang] = useState<Lang>("en");
  const [feedbackSent, setFeedbackSent] = useState<"accurate" | "notAccurate" | null>(null);
  const [sending, setSending] = useState(false);

  const advisory = useMemo(() => generateAdvisory(corrected, crop, stage), [corrected, crop, stage]);
  const text = advisory[lang];

  const tempDelta = +(corrected.tempMaxC - block.tempMaxC).toFixed(1);
  const rainDelta = +(corrected.rainfallMm - block.rainfallMm).toFixed(1);

  async function sendFeedback(accurate: boolean) {
    setSending(true);
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gpId: corrected.gpId, accurate }),
      });
      setFeedbackSent(accurate ? "accurate" : "notAccurate");
    } finally {
      setSending(false);
    }
  }

  const riskColor =
    advisory.riskLevel === "high" ? "#b91c1c" : advisory.riskLevel === "moderate" ? "#c9622b" : "#2f7d4f";

  return (
    <div className="h-full overflow-y-auto p-6 flex flex-col gap-6">
      <div>
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-wide text-[var(--ink)]/60">Selected panchayat</p>
          <button
            onClick={() => setLang(lang === "en" ? "mr" : "en")}
            className="text-xs px-2 py-1 rounded-full border border-[var(--ink)]/20 hover:bg-[var(--accent-soft)]"
          >
            {lang === "en" ? "मराठी" : "English"}
          </button>
        </div>
        <h2 className="text-2xl font-semibold">{gpName}</h2>
        <p className="text-sm text-[var(--ink)]/60">Elevation {elevationM} m</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-[var(--panel)] p-3 border border-[var(--ink)]/10">
          <p className="text-xs text-[var(--ink)]/60">Rainfall (corrected)</p>
          <p className="text-xl font-semibold">{corrected.rainfallMm} mm</p>
          <p className={`text-xs ${rainDelta >= 0 ? "text-[var(--warn)]" : "text-[var(--accent)]"}`}>
            {rainDelta >= 0 ? "+" : ""}
            {rainDelta} mm vs. block
          </p>
        </div>
        <div className="rounded-xl bg-[var(--panel)] p-3 border border-[var(--ink)]/10">
          <p className="text-xs text-[var(--ink)]/60">Max temp (corrected)</p>
          <p className="text-xl font-semibold">{corrected.tempMaxC}°C</p>
          <p className={`text-xs ${tempDelta >= 0 ? "text-[var(--warn)]" : "text-[var(--accent)]"}`}>
            {tempDelta >= 0 ? "+" : ""}
            {tempDelta}°C vs. block
          </p>
        </div>
        <div className="rounded-xl bg-[var(--panel)] p-3 border border-[var(--ink)]/10">
          <p className="text-xs text-[var(--ink)]/60">Min temp</p>
          <p className="text-xl font-semibold">{corrected.tempMinC}°C</p>
        </div>
        <div className="rounded-xl bg-[var(--panel)] p-3 border border-[var(--ink)]/10">
          <p className="text-xs text-[var(--ink)]/60">Humidity</p>
          <p className="text-xl font-semibold">{corrected.humidityPct}%</p>
        </div>
      </div>

      <div className="rounded-xl bg-[var(--panel)] p-4 border border-[var(--ink)]/10">
        <p className="text-xs uppercase tracking-wide text-[var(--ink)]/60 mb-2">Why this differs from the block forecast</p>
        <ul className="text-sm space-y-1.5 list-disc list-inside text-[var(--ink)]/80">
          {corrected.explanation.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>

      <div className="rounded-xl bg-[var(--panel)] p-4 border border-[var(--ink)]/10 flex flex-col gap-3">
        <p className="text-xs uppercase tracking-wide text-[var(--ink)]/60">Crop advisory</p>
        <div className="flex gap-2 flex-wrap">
          <select
            value={crop}
            onChange={(e) => setCrop(e.target.value as Crop)}
            className="text-sm rounded-lg border border-[var(--ink)]/20 px-2 py-1 bg-white"
          >
            {CROPS.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value as CropStage)}
            className="text-sm rounded-lg border border-[var(--ink)]/20 px-2 py-1 bg-white"
          >
            {STAGES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: riskColor }} />
          <p className="text-sm font-medium">{text.summary}</p>
        </div>
        <ul className="text-sm space-y-1.5 list-disc list-inside text-[var(--ink)]/80">
          {text.actions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      </div>

      <div className="rounded-xl bg-[var(--panel)] p-4 border border-[var(--ink)]/10">
        <p className="text-xs uppercase tracking-wide text-[var(--ink)]/60 mb-2">Was this forecast accurate?</p>
        {feedbackSent ? (
          <p className="text-sm text-[var(--accent)]">
            Thanks — logged as {feedbackSent === "accurate" ? "accurate" : "not accurate"}.
          </p>
        ) : (
          <div className="flex gap-2">
            <button
              disabled={sending}
              onClick={() => sendFeedback(true)}
              className="text-sm px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white disabled:opacity-50"
            >
              Accurate
            </button>
            <button
              disabled={sending}
              onClick={() => sendFeedback(false)}
              className="text-sm px-3 py-1.5 rounded-lg border border-[var(--ink)]/20 disabled:opacity-50"
            >
              Not accurate
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
