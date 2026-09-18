import { Panchayat, BLOCK, AWS_STATIONS } from "./panchayats";

export type BlockForecast = {
  date: string;
  rainfallMm: number;
  tempMaxC: number;
  tempMinC: number;
  humidityPct: number;
  windKmh: number;
};

export type Explanation = {
  elevationDeltaM: number;
  tempAdjustC: number;
  rainAdjustMm: number;
  humidityAdjustPct: number;
  stationResidualTempC: number;
  stationResidualRainMm: number;
  reasons: string[];
};

export type CorrectedForecast = BlockForecast & {
  gpId: string;
  explanation: Explanation;
};

const LAPSE_RATE_C_PER_1000M = 6.5; // standard environmental lapse rate
const OROGRAPHIC_RAIN_PCT_PER_100M = 0.045; // +4.5% rainfall per 100m elevation gain (orographic lift), demo coefficient
const FOREST_COOLING_C_PER_10PCT = 0.12; // denser canopy -> slightly cooler local surface temp
const RIVER_HUMIDITY_PCT_PER_KM = 0.6; // humidity falls off with distance from the river, demo coefficient

/** Great-circle distance in km via the haversine formula. */
function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/** Inverse-distance-weighted blend of historical AWS station bias — a lightweight,
 *  explainable stand-in for a kriging / ML residual-correction layer. */
function idwStationResidual(gp: Panchayat) {
  let wSum = 0;
  let tSum = 0;
  let rSum = 0;
  for (const s of AWS_STATIONS) {
    const d = haversineKm(gp.lat, gp.lon, s.lat, s.lon);
    const w = 1 / Math.max(d, 0.5) ** 2;
    wSum += w;
    tSum += w * s.tempResidualC;
    rSum += w * s.rainResidualMm;
  }
  return { tempResidualC: tSum / wSum, rainResidualMm: rSum / wSum };
}

/** Mock "today" raw block-level forecast — stands in for the single NWP grid
 *  value a coarse ~12km forecast (or a lookup portal) would return. */
export function getBlockForecast(): BlockForecast {
  return {
    date: new Date().toISOString().slice(0, 10),
    rainfallMm: 18.4,
    tempMaxC: 33.2,
    tempMinC: 23.5,
    humidityPct: 62,
    windKmh: 14,
  };
}

export function correctForGP(gp: Panchayat, block: BlockForecast): CorrectedForecast {
  const elevationDeltaM = gp.elevationM - BLOCK.elevationM;
  const tempAdjustC = -(elevationDeltaM / 1000) * LAPSE_RATE_C_PER_1000M;
  const rainAdjustMm = block.rainfallMm * (elevationDeltaM / 100) * OROGRAPHIC_RAIN_PCT_PER_100M;
  const forestAdjustC = -(gp.forestCoverPct / 10) * FOREST_COOLING_C_PER_10PCT;
  const humidityAdjustPct = -gp.distFromRiverKm * RIVER_HUMIDITY_PCT_PER_KM;
  const { tempResidualC, rainResidualMm } = idwStationResidual(gp);

  const tempMaxC = +(block.tempMaxC + tempAdjustC + forestAdjustC + tempResidualC).toFixed(1);
  const tempMinC = +(block.tempMinC + tempAdjustC + forestAdjustC + tempResidualC * 0.6).toFixed(1);
  const rainfallMm = Math.max(0, +(block.rainfallMm + rainAdjustMm + rainResidualMm).toFixed(1));
  const humidityPct = Math.min(100, Math.max(10, Math.round(block.humidityPct + humidityAdjustPct)));

  const reasons: string[] = [];
  reasons.push(
    elevationDeltaM >= 0
      ? `${gp.name} sits ${elevationDeltaM.toFixed(0)} m higher than the reference grid, cooling max temp by ${Math.abs(tempAdjustC).toFixed(1)}°C (lapse rate) and lifting rainfall by ${rainAdjustMm.toFixed(1)} mm (orographic effect).`
      : `${gp.name} sits ${Math.abs(elevationDeltaM).toFixed(0)} m lower than the reference grid, warming max temp by ${Math.abs(tempAdjustC).toFixed(1)}°C.`
  );
  if (gp.forestCoverPct > 10) {
    reasons.push(`${gp.forestCoverPct}% forest cover adds local canopy cooling of ${Math.abs(forestAdjustC).toFixed(2)}°C.`);
  }
  reasons.push(`${gp.distFromRiverKm} km from the Krishna river corridor shifts humidity by ${humidityAdjustPct.toFixed(1)} pts.`);
  reasons.push(`Nearby AWS station history nudges temp by ${tempResidualC.toFixed(2)}°C and rainfall by ${rainResidualMm.toFixed(1)} mm (bias correction).`);

  return {
    date: block.date,
    tempMaxC,
    tempMinC,
    rainfallMm,
    humidityPct,
    windKmh: block.windKmh,
    gpId: gp.id,
    explanation: {
      elevationDeltaM: +elevationDeltaM.toFixed(0),
      tempAdjustC: +tempAdjustC.toFixed(2),
      rainAdjustMm: +rainAdjustMm.toFixed(1),
      humidityAdjustPct: +humidityAdjustPct.toFixed(1),
      stationResidualTempC: +tempResidualC.toFixed(2),
      stationResidualRainMm: +rainResidualMm.toFixed(1),
      reasons,
    },
  };
}
