"use client";

import { useEffect, useRef, useState } from "react";
import { audioUrl, loadAdvisory, type Source } from "@/lib/api";
import type { Advisory, Lang, Options } from "@/lib/types";

export type AdvisoryChoice = { crop: string; stage: string; lang: Lang };

export const LANG_FONT: Record<Lang, string> = {
  en: "",
  hi: "font-[family-name:var(--font-hi)] text-[1.05em]",
  mr: "font-[family-name:var(--font-mr)] text-[1.05em]",
};

/** Crop / stage / language pickers. */
export function AdvisoryControls({
  options,
  value,
  onChange,
}: {
  options: Options;
  value: AdvisoryChoice;
  onChange: (v: AdvisoryChoice) => void;
}) {
  const sel = "w-full rounded border border-line bg-card px-2 py-1.5 text-sm";
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_1fr_auto]">
      <label className="text-xs text-muted">
        Crop
        <select className={sel} value={value.crop} onChange={(e) => onChange({ ...value, crop: e.target.value })}>
          {Object.entries(options.crops).map(([k, n]) => (
            <option key={k} value={k}>
              {n.en}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs text-muted">
        Stage
        <select className={sel} value={value.stage} onChange={(e) => onChange({ ...value, stage: e.target.value })}>
          {Object.entries(options.stages).map(([k, n]) => (
            <option key={k} value={k}>
              {n.en[0].toUpperCase() + n.en.slice(1)}
            </option>
          ))}
        </select>
      </label>
      <div className="col-span-2 text-xs text-muted sm:col-span-1">
        Language
        <div className="mt-px flex overflow-hidden rounded border border-line" role="radiogroup" aria-label="Language">
          {(["en", "hi", "mr"] as Lang[]).map((l) => (
            <button
              key={l}
              role="radio"
              aria-checked={value.lang === l}
              onClick={() => onChange({ ...value, lang: l })}
              className={`flex-1 px-3 py-1.5 text-sm ${value.lang === l ? "bg-navy text-white" : "bg-card text-ink hover:bg-navy-soft"}`}
            >
              {options.langs[l] === "English" ? "EN" : options.langs[l]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Loads the advisory for a choice. Loading = the last result belongs to an older request. */
export function useAdvisory(panchayatId: string | null, choice: AdvisoryChoice, preferSnapshot: boolean) {
  const key = `${panchayatId}|${choice.crop}|${choice.stage}|${choice.lang}|${preferSnapshot}`;
  const [res, setRes] = useState<{ key: string; adv: Advisory | null; source: Source | null; error: string | null } | null>(
    null,
  );
  useEffect(() => {
    if (!panchayatId) return;
    let live = true;
    loadAdvisory(panchayatId, choice.crop, choice.stage, choice.lang, preferSnapshot)
      .then((r) => live && setRes({ key, adv: r.data, source: r.source, error: null }))
      .catch((e) => live && setRes({ key, adv: null, source: null, error: String(e.message ?? e) }));
    return () => {
      live = false;
    };
  }, [key, panchayatId, choice.crop, choice.stage, choice.lang, preferSnapshot]);
  const loading = !res || res.key !== key;
  return {
    adv: loading ? null : res.adv,
    source: loading ? null : res.source,
    error: loading ? null : res.error,
    loading,
  };
}

/** Play button for the gTTS voice advisory. Only offered when the live API is reachable.
 *  The parent gives it a `key` per selection, so a new selection starts from "idle". */
export function VoiceButton({ panchayatId, choice, enabled }: { panchayatId: string; choice: AdvisoryChoice; enabled: boolean }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const src = audioUrl(panchayatId, choice.crop, choice.stage, choice.lang);

  useEffect(() => {
    const el = audio.current;
    return () => el?.pause(); // stop speaking when the selection changes or the panel closes
  }, []);

  if (!enabled)
    return <p className="text-xs text-muted">Voice needs the live server; the offline copy has text only.</p>;

  const toggle = () => {
    if (!audio.current) return;
    if (status === "playing") {
      audio.current.pause();
      setStatus("idle");
      return;
    }
    setStatus("loading");
    audio.current.src = src;
    audio.current.play().then(() => setStatus("playing")).catch(() => setStatus("error"));
  };

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={toggle}
        className="flex items-center gap-2 rounded-full bg-forest px-4 py-2 text-sm font-medium text-white hover:bg-forest/90 disabled:opacity-60"
        disabled={status === "loading"}
      >
        <span aria-hidden>{status === "playing" ? "❚❚" : "▶"}</span>
        {status === "loading" ? "Preparing audio…" : status === "playing" ? "Pause" : "Play voice advisory"}
      </button>
      {status === "error" && <span className="text-xs text-danger">Voice service unreachable. Text advisory still works.</span>}
      <audio ref={audio} onEnded={() => setStatus("idle")} onError={() => status !== "idle" && setStatus("error")} />
    </div>
  );
}
