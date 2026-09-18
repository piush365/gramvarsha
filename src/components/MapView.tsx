"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { CorrectedForecast } from "@/lib/downscale";
import { Panchayat } from "@/lib/panchayats";

export type GpWithForecast = Panchayat & { corrected: CorrectedForecast };

function rainColor(mm: number) {
  if (mm > 40) return "#b91c1c";
  if (mm > 25) return "#c9622b";
  if (mm > 12) return "#2f7d4f";
  return "#5b8a6b";
}

export default function MapView({
  panchayats,
  selectedId,
  onSelect,
  mode,
  blockRain,
}: {
  panchayats: GpWithForecast[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  mode: "block" | "corrected";
  blockRain: number;
}) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const markersRef = useRef<Record<string, L.CircleMarker>>({});

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { zoomControl: true }).setView([17.0, 74.7], 9);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};

    panchayats.forEach((gp) => {
      const value = mode === "block" ? blockRain : gp.corrected.rainfallMm;
      const marker = L.circleMarker([gp.lat, gp.lon], {
        radius: gp.id === selectedId ? 12 : 8,
        color: gp.id === selectedId ? "#1b2a1f" : "#ffffff",
        weight: gp.id === selectedId ? 3 : 1,
        fillColor: rainColor(value),
        fillOpacity: 0.9,
      })
        .addTo(map)
        .bindTooltip(`${gp.name}: ${value.toFixed(1)} mm`, { direction: "top" })
        .on("click", () => onSelect(gp.id));
      markersRef.current[gp.id] = marker;
    });
  }, [panchayats, selectedId, mode, blockRain, onSelect]);

  return <div ref={containerRef} className="w-full h-full rounded-xl overflow-hidden" />;
}
