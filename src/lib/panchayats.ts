export type Panchayat = {
  id: string;
  name: string;
  block: string;
  lat: number;
  lon: number;
  elevationM: number;
  distFromRiverKm: number;
  forestCoverPct: number;
};

export type AwsStation = {
  name: string;
  lat: number;
  lon: number;
  // Historical mean bias of the raw NWP grid vs. this station's recorded readings.
  tempResidualC: number;
  rainResidualMm: number;
};

// Reference point for the raw ~12km NWP grid cell that covers central Sangli —
// this is the single value a coarse-resolution forecast (or a lookup tool like
// IMD's KALP) would return for every panchayat inside the cell.
export const BLOCK = {
  name: "Sangli–Miraj Block (12 km NWP grid reference)",
  lat: 16.8524,
  lon: 74.5815,
  elevationM: 550,
};

export const AWS_STATIONS: AwsStation[] = [
  { name: "Sangli AWS", lat: 16.8548, lon: 74.5815, tempResidualC: 0.1, rainResidualMm: -1.2 },
  { name: "Vita AWS", lat: 17.2833, lon: 74.5333, tempResidualC: -0.3, rainResidualMm: 2.4 },
  { name: "Shirala AWS", lat: 16.9167, lon: 73.9667, tempResidualC: -0.6, rainResidualMm: 6.1 },
  { name: "Jat AWS", lat: 17.05, lon: 75.2167, tempResidualC: 0.5, rainResidualMm: -3.8 },
];

export const PANCHAYATS: Panchayat[] = [
  { id: "sangliwadi", name: "Sangliwadi", block: "Miraj", lat: 16.8524, lon: 74.5815, elevationM: 560, distFromRiverKm: 0.5, forestCoverPct: 5 },
  { id: "miraj", name: "Miraj", block: "Miraj", lat: 16.8298, lon: 74.6453, elevationM: 555, distFromRiverKm: 3.2, forestCoverPct: 8 },
  { id: "palus", name: "Palus", block: "Palus", lat: 16.9333, lon: 74.4667, elevationM: 550, distFromRiverKm: 2.0, forestCoverPct: 6 },
  { id: "kavathe-mahankal", name: "Kavathe Mahankal", block: "Kavathe Mahankal", lat: 17.098, lon: 74.933, elevationM: 610, distFromRiverKm: 18.0, forestCoverPct: 12 },
  { id: "vita", name: "Vita", block: "Khanapur", lat: 17.2833, lon: 74.5333, elevationM: 585, distFromRiverKm: 22.0, forestCoverPct: 15 },
  { id: "shirala", name: "Shirala", block: "Shirala", lat: 16.9167, lon: 73.9667, elevationM: 640, distFromRiverKm: 35.0, forestCoverPct: 45 },
  { id: "jat", name: "Jat", block: "Jat", lat: 17.05, lon: 75.2167, elevationM: 585, distFromRiverKm: 40.0, forestCoverPct: 3 },
  { id: "khanapur", name: "Khanapur", block: "Khanapur", lat: 17.2, lon: 74.75, elevationM: 615, distFromRiverKm: 15.0, forestCoverPct: 20 },
];
