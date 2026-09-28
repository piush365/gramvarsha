"use client";

// Per-panchayat error map for /validation: % RMSE improvement of GramVarsha over the
// raw block forecast on the held-out months. Diverging: blue = better than block,
// amber = worse, grey = no change.

import L from "leaflet";
import { useEffect } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import { improvementColour } from "@/lib/scale";
import type { Geo, Validation, Var } from "@/lib/types";


function Fit({ geo }: { geo: Geo }) {
  const map = useMap();
  useEffect(() => {
    const b = L.geoJSON(geo.taluka_boundary).getBounds();
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(b, { padding: [6, 6] });
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(map.getContainer());
    return () => ro.disconnect();
  }, [geo, map]);
  return null;
}

export default function ErrorMap({ geo, validation, variable, maxAbs }: {
  geo: Geo;
  validation: Validation;
  variable: Var;
  maxAbs: number;
}) {
  const pv = validation.per_village_temporal_rmse;
  const pct = (id: string) => {
    const r = pv[id]?.[variable];
    return r ? 100 * (1 - r.final / r.block) : 0;
  };
  return (
    <MapContainer center={[16.86, 74.69]} zoom={10} zoomSnap={0.25} scrollWheelZoom={false} className="h-full w-full">
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        className="gv-basemap"
      />
      <Fit geo={geo} />
      <GeoJSON
        key={variable}
        data={geo.voronoi}
        style={(f) => ({
          fillColor: improvementColour(pct(f?.properties?.id), maxAbs),
          fillOpacity: 0.9,
          color: "#ffffff",
          weight: 1,
        })}
        onEachFeature={(f, layer) => {
          const id = f.properties.id as string;
          const r = pv[id]?.[variable];
          layer.bindTooltip(
            r
              ? `<strong>${f.properties.name}</strong><br/>RMSE block ${r.block.toFixed(2)} → GramVarsha ${r.final.toFixed(2)} (${pct(id) >= 0 ? "−" : "+"}${Math.abs(pct(id)).toFixed(0)}% error)`
              : f.properties.name,
            { sticky: true },
          );
        }}
      />
      <GeoJSON data={geo.taluka_boundary} style={{ color: "#1B3A5C", weight: 2, fill: false, interactive: false }} />
    </MapContainer>
  );
}
