"use client";

// What a farmer actually receives. No app, no login, nothing to type:
// an SMS on any phone, the same advisory on WhatsApp, and a voice call in their language.

import { useEffect, useState } from "react";
import { AdvisoryControls, LANG_FONT, useAdvisory, VoiceButton, type AdvisoryChoice } from "@/components/AdvisoryCard";
import StatusBanner from "@/components/StatusBanner";
import { loadForecast, loadOptions, sendFeedback, type Source } from "@/lib/api";
import type { Forecast, Lang, Options, Panchayat } from "@/lib/types";

const SENDER = { en: "GramVarsha", hi: "ग्रामवर्षा", mr: "ग्रामवर्षा" };

export default function FarmerPage() {
  const [data, setData] = useState<{ forecast: Forecast; options: Options; source: Source } | null>(null);
  const [pid, setPid] = useState("mhaisal");
  const [choice, setChoice] = useState<AdvisoryChoice>({ crop: "grapes", stage: "flowering", lang: "mr" });

  useEffect(() => {
    Promise.all([loadForecast(), loadOptions()]).then(([f, o]) =>
      setData({ forecast: f.data, options: o.data, source: f.source === "live" && o.source === "live" ? "live" : "snapshot" }),
    );
  }, []);

  const p = data?.forecast.panchayats.find((x) => x.id === pid) ?? data?.forecast.panchayats[0] ?? null;
  const { adv, loading, error, source: advSource } = useAdvisory(p?.id ?? null, choice, data?.source === "snapshot");

  return (
    <>
      {data && (
        <StatusBanner
          source={data.source}
          generatedAt={data.forecast.generated_at}
          stale={data.forecast.stale}
          staleSince={data.forecast.stale_since}
        />
      )}
      <main className="mx-auto grid w-full max-w-6xl flex-1 gap-8 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-12">
        <section className="space-y-5">
          <p className="eyebrow">Farmer view</p>
          <h1 className="text-2xl font-semibold leading-tight sm:text-3xl">
            The farmer installs nothing and types nothing.
          </h1>
          <p className="max-w-prose text-muted">
            Each morning the advisory for their own panchayat and crop reaches them three ways: an SMS that works on a
            basic keypad phone, the same message on WhatsApp, and a voice call read out in Marathi or Hindi for those
            who prefer to listen. Replying <strong className="text-ink">1</strong> or <strong className="text-ink">2</strong>{" "}
            tells us whether the forecast was right.
          </p>

          <div className="space-y-3 rounded-lg border border-line bg-card p-4">
            <p className="eyebrow">Try it for a farmer in</p>
            {data ? (
              <>
                <label className="block text-xs text-muted">
                  Panchayat
                  <select
                    value={p?.id}
                    onChange={(e) => setPid(e.target.value)}
                    className="mt-px w-full rounded border border-line bg-card px-2 py-1.5 text-sm"
                  >
                    {data.forecast.panchayats.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.name} · {x.name_mr}
                      </option>
                    ))}
                  </select>
                </label>
                <AdvisoryControls options={data.options} value={choice} onChange={setChoice} />
              </>
            ) : (
              <div className="skeleton h-24 w-full" />
            )}
          </div>

          <dl className="grid gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="font-semibold">SMS</dt>
              <dd className="text-muted">Fits one message. Any phone, no internet. Sent through a bulk SMS gateway.</dd>
            </div>
            <div>
              <dt className="font-semibold">WhatsApp</dt>
              <dd className="text-muted">Two-day forecast plus every action for the chosen crop and stage.</dd>
            </div>
            <div>
              <dt className="font-semibold">Voice call</dt>
              <dd className="text-muted">The same advice spoken aloud (gTTS here; an IVR line in production).</dd>
            </div>
          </dl>
        </section>

        <Phone>
          {!p || loading ? (
            <div className="space-y-3 p-4">
              <div className="skeleton h-20 w-4/5" />
              <div className="skeleton h-40 w-full" />
            </div>
          ) : error ? (
            <p className="p-4 text-sm text-danger">{error}</p>
          ) : (
            adv && (
              <Inbox
                key={`${p.id}-${choice.lang}`}
                p={p}
                lang={choice.lang}
                sms={adv.sms}
                whatsapp={adv.whatsapp}
                voice={<VoiceButton key={`${p.id}-${choice.crop}-${choice.stage}-${choice.lang}`} panchayatId={p.id} choice={choice} enabled={advSource === "live"} />}
                canReply={data?.source === "live"}
              />
            )
          )}
        </Phone>
      </main>
    </>
  );
}

function Phone({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[360px]">
      <div className="rounded-[2.4rem] bg-ink p-2.5 shadow-xl">
        <div className="overflow-hidden rounded-[1.9rem] bg-[#ECE5DD]">
          <div className="flex items-center justify-between bg-navy px-5 pb-2 pt-3 text-[11px] text-white/80">
            <span className="num">07:02</span>
            <span className="h-4 w-16 rounded-full bg-ink" aria-hidden />
            <span>4G ▮▮▮</span>
          </div>
          <div className="h-[640px] overflow-y-auto">{children}</div>
        </div>
      </div>
    </div>
  );
}

function Inbox(props: {
  p: Panchayat;
  lang: Lang;
  sms: string;
  whatsapp: string;
  voice: React.ReactNode;
  canReply: boolean;
}) {
  const { p, lang, sms, whatsapp, voice, canReply } = props;
  const [replied, setReplied] = useState<null | "1" | "2" | "error">(null);
  const font = LANG_FONT[lang];
  const reply = async (r: "1" | "2") => {
    try {
      await sendFeedback({
        panchayat_id: p.id,
        date: p.days[0].date,
        variable: "overall",
        rating: r === "1" ? "accurate" : "not_accurate",
        channel: "sms",
      });
      setReplied(r);
    } catch {
      setReplied("error");
    }
  };

  return (
    <div className="space-y-4 p-3 text-[13px]">
      {/* Voice call */}
      <div className="rounded-2xl bg-navy p-4 text-white">
        <p className="text-[11px] uppercase tracking-wider text-white/60">Incoming voice advisory</p>
        <p className="mt-1 text-base font-semibold">
          {SENDER[lang]} · <span className={font}>{lang === "en" ? p.name : lang === "hi" ? p.name_hi : p.name_mr}</span>
        </p>
        <div className="mt-3 [&_button]:bg-amber [&_button]:text-ink [&_p]:text-white/70 [&_span]:text-white/80">{voice}</div>
      </div>

      {/* SMS */}
      <div>
        <p className="mb-1 text-center text-[11px] text-muted">SMS · {SENDER[lang]}</p>
        <div className={`max-w-[88%] rounded-2xl rounded-tl-sm bg-white p-3 shadow-sm ${font}`}>{sms}</div>
        <div className="mt-2 flex justify-end gap-2">
          {replied === "1" || replied === "2" ? (
            <div className="rounded-2xl rounded-tr-sm bg-navy px-3 py-2 text-white">{replied}</div>
          ) : canReply ? (
            <>
              <button onClick={() => reply("1")} className="rounded-full border border-navy/30 bg-white px-3 py-1 text-xs">
                Reply 1 · right
              </button>
              <button onClick={() => reply("2")} className="rounded-full border border-navy/30 bg-white px-3 py-1 text-xs">
                Reply 2 · wrong
              </button>
            </>
          ) : (
            <span className="text-[11px] text-muted">Replies need the live server.</span>
          )}
        </div>
        {(replied === "1" || replied === "2") && (
          <p className="mt-1 text-right text-[11px] text-forest">Saved as SMS feedback; visible to the officer.</p>
        )}
        {replied === "error" && <p className="mt-1 text-right text-[11px] text-danger">Reply not saved. Try again.</p>}
      </div>

      {/* WhatsApp */}
      <div>
        <p className="mb-1 text-center text-[11px] text-muted">WhatsApp</p>
        <div className={`max-w-[94%] whitespace-pre-line rounded-2xl rounded-tl-sm bg-[#DCF8C6] p-3 leading-relaxed shadow-sm ${font}`}>
          {whatsapp}
        </div>
      </div>
    </div>
  );
}
