"use client";

import { useState } from "react";
import { sendFeedback, type Source } from "@/lib/api";
import { fmt, fmtDay, UNIT, VAR_LABEL } from "@/lib/scale";
import { VARS, type Options, type Panchayat, type Validation, type Var } from "@/lib/types";
import { AdvisoryControls, LANG_FONT, useAdvisory, VoiceButton, type AdvisoryChoice } from "./AdvisoryCard";
import WhyBars from "./WhyBars";

type Props = {
  p: Panchayat;
  day: number;
  variable: Var;
  onVariable: (v: Var) => void;
  options: Options;
  validation: Validation | null;
  source: Source;
};

const TIER_STYLE = { A: "bg-navy text-white", B: "bg-amber text-ink", C: "bg-amber text-ink" };

export default function PanchayatPanel({ p, day, variable, onVariable, options, validation, source }: Props) {
  const d = p.days[day];
  const v = d.values[variable];
  const verdict = validation?.verdict[variable];
  const [choice, setChoice] = useState<AdvisoryChoice>({ crop: "grapes", stage: "flowering", lang: "mr" });
  const { adv, error, loading, source: advSource } = useAdvisory(p.id, choice, source === "snapshot");

  return (
    <div className="flex flex-col divide-y divide-line">
      {/* Identity */}
      <section className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold leading-tight">{p.name}</h2>
            <p className="font-[family-name:var(--font-mr)] text-lg text-muted">{p.name_mr}</p>
          </div>
          <span className={`rounded px-2 py-0.5 text-xs font-semibold ${TIER_STYLE[p.tier]}`} title={p.tier_text}>
            Tier {p.tier}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted">
          {p.elevation_m !== null && <>Elevation {Math.round(p.elevation_m)} m · </>}
          {p.dist_river_km !== null && <>{p.dist_river_km.toFixed(1)} km from the Krishna · </>}
          {p.tier_text}
        </p>
      </section>

      {/* Block vs downscaled */}
      <section className="p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="eyebrow">{fmtDay(d.date, d.lead)} · block vs this panchayat</h3>
          {!d.validated && <span className="text-[11px] text-amber">day {d.lead + 1}: not validated</span>}
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] text-muted">
              <th className="py-1 font-normal" />
              <th className="py-1 text-right font-normal">Block</th>
              <th className="py-1 text-right font-normal">GramVarsha</th>
              <th className="py-1 text-right font-normal">likely range</th>
            </tr>
          </thead>
          <tbody>
            {VARS.map((k) => {
              const x = d.values[k];
              const active = k === variable;
              return (
                <tr
                  key={k}
                  onClick={() => onVariable(k)}
                  className={`cursor-pointer border-t border-line ${active ? "bg-amber-soft" : "hover:bg-paper"}`}
                >
                  <td className="py-1.5 pl-1">
                    {VAR_LABEL[k]} <span className="text-[11px] text-muted">{UNIT[k]}</span>
                  </td>
                  <td className="num py-1.5 text-right text-muted">{fmt(k, x.block)}</td>
                  <td className="num py-1.5 text-right font-medium">{fmt(k, x.value)}</td>
                  <td className="num py-1.5 pr-1 text-right text-[12px] text-muted">
                    {x.band ? `${fmt(k, x.band[0])}–${fmt(k, x.band[1])}` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-1 text-[11px] text-muted">Range = 10th–90th percentile of past errors on validation weeks.</p>
      </section>

      {/* Why different */}
      <section className="p-4">
        <h3 className="eyebrow mb-1">Why different? · {VAR_LABEL[variable].toLowerCase()}</h3>
        <p className="mb-3 text-sm">{v.explanation.sentence}</p>
        {v.explanation.parts.length > 0 && <WhyBars ex={v.explanation} />}
        {v.explanation.note && <p className="mt-2 text-[11px] text-muted">{v.explanation.note}</p>}
        {verdict && !verdict.resolves_village_differences && (
          <p className="mt-3 rounded bg-navy-soft px-3 py-2 text-xs text-navy">
            Validation shows this variable improves on the block forecast mainly as a block-wide correction; the
            differences between villages are not yet reliable. See Validation.
          </p>
        )}
      </section>

      {/* Advisory */}
      <section className="space-y-3 p-4">
        <h3 className="eyebrow">Advisory</h3>
        <AdvisoryControls options={options} value={choice} onChange={setChoice} />
        <div className={`min-h-24 rounded border border-line bg-paper p-3 text-sm leading-relaxed ${LANG_FONT[choice.lang]}`}>
          {loading && <div className="skeleton h-16 w-full" />}
          {error && <p className="font-sans text-danger">{error}</p>}
          {adv && !loading && (
            <ul className="space-y-1.5">
              {adv.lines.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          )}
          {adv?.polished && <p className="mt-2 border-t border-line pt-2 italic">{adv.polished}</p>}
        </div>
        {adv && (
          <p className="text-[11px] text-muted">
            SMS ({adv.sms_chars} chars): <span className={LANG_FONT[choice.lang]}>{adv.sms}</span>
          </p>
        )}
        <VoiceButton key={`${p.id}-${choice.crop}-${choice.stage}-${choice.lang}`} panchayatId={p.id} choice={choice} enabled={advSource === "live"} />
      </section>

      <Feedback key={`${p.id}-${d.date}-${variable}`} p={p} date={d.date} variable={variable} enabled={source === "live"} />
    </div>
  );
}

function Feedback({ p, date, variable, enabled }: { p: Panchayat; date: string; variable: Var; enabled: boolean }) {
  const [sent, setSent] = useState<null | "accurate" | "not_accurate" | "error">(null);
  const send = async (rating: "accurate" | "not_accurate") => {
    try {
      await sendFeedback({ panchayat_id: p.id, date, variable, rating, channel: "web" });
      setSent(rating);
    } catch {
      setSent("error");
    }
  };
  return (
    <section className="p-4">
      <h3 className="eyebrow mb-2">Was this forecast right for {p.name}?</h3>
      {!enabled ? (
        <p className="text-xs text-muted">Feedback needs the live server.</p>
      ) : sent === "accurate" || sent === "not_accurate" ? (
        <p className="text-sm text-forest">Feedback saved. It appears in the officer view.</p>
      ) : (
        <div className="flex gap-2">
          <button onClick={() => send("accurate")} className="rounded border border-line px-3 py-1.5 text-sm hover:bg-forest-soft">
            👍 Accurate
          </button>
          <button onClick={() => send("not_accurate")} className="rounded border border-line px-3 py-1.5 text-sm hover:bg-amber-soft">
            👎 Not accurate
          </button>
          {sent === "error" && <span className="self-center text-xs text-danger">Could not save. Try again.</span>}
        </div>
      )}
    </section>
  );
}
