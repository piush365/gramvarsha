"use client";

// Leaflet map of the approximate panchayat polygons, coloured by the selected variable.
// Layers are created once and restyled in place (setStyle), so switching between
// "Block forecast" and "GramVarsha downscaled" animates the fills via CSS.

import L from "leaflet";
import { useEffect, useMemo, useRef } from "react";
import { GeoJSON, MapContainer, Rectangle, TileLayer, Tooltip, useMap } from "react-leaflet";
import { colour, fmt, norm, UNIT, type Domain } from "@/lib/scale";
import type { Block, Geo, Panchayat, Var } from "@/lib/types";

type Props = {
  geo: Geo;
  block: Block;
  panchayats: Panchayat[];
  variable: Var;
  day: number;
  mode: "block" | "downscaled";
  domain: Domain;
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function FitToTaluka({ geo }: { geo: Geo }) {
  const map = useMap();
  useEffect(() => {
    const b = L.geoJSON(geo.taluka_boundary).getBounds();
    // Re-fit whenever the container changes size (first layout, rotation, panel resize).
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(b, { padding: [8, 8] });
    };
    fit();
    const late = window.setTimeout(fit, 400); // after fonts/panels settle
    const ro = new ResizeObserver(fit);
    ro.observe(map.getContainer());
    return () => {
      ro.disconnect();
      window.clearTimeout(late);
    };
  }, [geo, map]);
  return null;
}

/** Small A/B/C tier badges at each village point. */
function TierBadges({ panchayats }: { panchayats: Panchayat[] }) {
  const map = useMap();
  useEffect(() => {
    const layer = L.layerGroup(
      panchayats.map((p) =>
        L.marker([p.lat, p.lon], {
          interactive: false,
          keyboard: false,
          icon: L.divIcon({ className: "", html: `<div class="gv-tier tier-${p.tier}">${p.tier}</div>`, iconSize: [14, 14] }),
        }),
      ),
    ).addTo(map);
    return () => {
      layer.remove();
    };
  }, [map, panchayats]);
  return null;
}

export default function ForecastMap(props: Props) {
  const { geo, block, panchayats, variable, day, mode, domain, selectedId, onSelect } = props;
  const layers = useRef(new Map<string, L.Path>());
  const byId = useMemo(() => new Map(panchayats.map((p) => [p.id, p])), [panchayats]);
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  const styleFor = (id: string): L.PathOptions => {
    const p = byId.get(id);
    const v = p?.days[day]?.values[variable];
    const x = v ? (mode === "block" ? v.block : v.value) : null;
    const selected = id === selectedId;
    return {
      className: "gv-cell",
      fillColor: x === null ? "#ccc" : colour(variable, norm(domain, x)),
      fillOpacity: 0.88,
      color: selected ? "#1B3A5C" : "#ffffff",
      weight: selected ? 3 : 1,
    };
  };

  // Restyle in place whenever the view changes.
  useEffect(() => {
    layers.current.forEach((layer, id) => {
      layer.setStyle(styleFor(id));
      if (id === selectedId) layer.bringToFront();
      const p = byId.get(id);
      const v = p?.days[day]?.values[variable];
      if (p && v) {
        const x = mode === "block" ? v.block : v.value;
        layer.setTooltipContent(`<strong>${p.name}</strong> · ${fmt(variable, x)} ${UNIT[variable]}`);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variable, day, mode, domain, selectedId, byId]);

  const cell = block.gfs_cell;
  const h = cell.size_deg / 2;

  return (
    <MapContainer
      center={[block.lat, block.lon]}
      zoom={10}
      zoomSnap={0.25}
      scrollWheelZoom={false}
      attributionControl
      className="h-full w-full"
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        className="gv-basemap"
      />
      <FitToTaluka geo={geo} />
      <GeoJSON
        data={geo.voronoi}
        style={(f) => styleFor(f?.properties?.id)}
        onEachFeature={(f, layer) => {
          const id = f.properties.id as string;
          layers.current.set(id, layer as L.Path);
          layer.bindTooltip(f.properties.name, { sticky: true, direction: "top" });
          layer.on("click", () => onSelectRef.current(id));
          layer.on("keypress", () => onSelectRef.current(id));
        }}
      />
      <GeoJSON
        data={geo.taluka_boundary}
        style={{ color: "#1B3A5C", weight: 2, fill: false, interactive: false }}
      />
      <GeoJSON data={geo.rivers} style={{ color: "#3f7fb5", weight: 3, opacity: 0.8, interactive: false }} />
      <Rectangle
        bounds={[
          [cell.lat - h, cell.lon - h],
          [cell.lat + h, cell.lon + h],
        ]}
        pathOptions={{ color: "#E3A33B", weight: 2.5, dashArray: "8 6", fill: false, interactive: false }}
      />
      <Tooltip permanent direction="top" className="gv-cell-label" position={[cell.lat + h, cell.lon]}>
        Coarse forecast cell · 0.25° (~27 km)
      </Tooltip>
      <TierBadges panchayats={panchayats} />
    </MapContainer>
  );
}
