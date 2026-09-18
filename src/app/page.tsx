"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import ForecastPanel from "@/components/ForecastPanel";
import { CorrectedForecast, BlockForecast } from "@/lib/downscale";
import { Panchayat } from "@/lib/panchayats";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

type GpWithForecast = Panchayat & { corrected: CorrectedForecast };

type ApiResponse = {
  block: { name: string; forecast: BlockForecast; referenceElevationM: number };
  panchayats: GpWithForecast[];
};

export default function Home() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [mode, setMode] = useState<"block" | "corrected">("corrected");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/panchayats")
      .then((r) => r.json())
      .then((d: ApiResponse) => {
        setData(d);
        setSelectedId(d.panchayats[0].id);
      });
  }, []);

  const selected = data?.panchayats.find((p) => p.id === selectedId) ?? null;

  const spread = data
    ? +(
        Math.max(...data.panchayats.map((p) => p.corrected.rainfallMm)) -
        Math.min(...data.panchayats.map((p) => p.corrected.rainfallMm))
      ).toFixed(1)
    : 0;

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg)]">
        <p className="text-sm text-[var(--ink)]/60">Loading forecast…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-[var(--bg)]">
      <header className="border-b border-[var(--ink)]/10 bg-[var(--panel)] px-6 py-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">GramVarsha</h1>
          <p className="text-sm text-[var(--ink)]/60">
            Terrain-aware forecast downscaling for {data.panchayats.length} panchayats around Sangli
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-[var(--ink)]/70">
            Block forecast: <span className="font-medium">{data.block.forecast.rainfallMm} mm</span> ·{" "}
            <span className="font-medium">{data.block.forecast.tempMaxC}°C</span>
          </div>
          <div className="text-sm rounded-full bg-[var(--accent-soft)] text-[var(--accent)] px-3 py-1">
            Panchayat spread: {spread} mm
          </div>
          <div className="flex rounded-full border border-[var(--ink)]/15 overflow-hidden text-sm">
            <button
              onClick={() => setMode("block")}
              className={`px-3 py-1.5 ${mode === "block" ? "bg-[var(--accent)] text-white" : "bg-white"}`}
            >
              Raw block
            </button>
            <button
              onClick={() => setMode("corrected")}
              className={`px-3 py-1.5 ${mode === "corrected" ? "bg-[var(--accent)] text-white" : "bg-white"}`}
            >
              Corrected
            </button>
          </div>
        </div>
      </header>

      <main className="flex flex-1 flex-col lg:flex-row gap-4 p-4 min-h-0">
        <div className="flex-1 flex flex-col gap-4 min-h-0">
          <div className="flex-1 min-h-[360px] rounded-xl border border-[var(--ink)]/10 overflow-hidden">
            <MapView
              panchayats={data.panchayats}
              selectedId={selectedId}
              onSelect={setSelectedId}
              mode={mode}
              blockRain={data.block.forecast.rainfallMm}
            />
          </div>
          <div className="rounded-xl border border-[var(--ink)]/10 bg-[var(--panel)] p-3">
            <div className="flex flex-wrap gap-2">
              {data.panchayats.map((gp) => (
                <button
                  key={gp.id}
                  onClick={() => setSelectedId(gp.id)}
                  className={`text-sm px-3 py-1.5 rounded-full border ${
                    gp.id === selectedId
                      ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                      : "border-[var(--ink)]/15 hover:bg-[var(--accent-soft)]"
                  }`}
                >
                  {gp.name} · {gp.corrected.rainfallMm} mm
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:w-[420px] rounded-xl border border-[var(--ink)]/10 bg-[var(--panel)] overflow-hidden">
          {selected && (
            <ForecastPanel
              gpName={selected.name}
              elevationM={selected.elevationM}
              block={data.block.forecast}
              corrected={selected.corrected}
            />
          )}
        </div>
      </main>
    </div>
  );
}
