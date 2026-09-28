// Shapes of the GramVarsha API responses (see backend/main.py and backend/forecast.py).

export const VARS = ["rain", "tmax", "tmin", "rh", "wind"] as const;
export type Var = (typeof VARS)[number];
export type Lang = "en" | "hi" | "mr";
export type Tier = "A" | "B" | "C";

export type Part = { label: string; value: number; kind: "local" | "block-wide" };

export type Explanation = {
  delta: number;
  unit: string;
  parts: Part[];
  sentence: string;
  note: string | null;
  local_share: number;
};

export type Value = {
  block: number;
  value: number;
  band: [number, number] | null;
  explanation: Explanation;
};

export type Day = { date: string; lead: number; validated: boolean; values: Record<Var, Value> };

export type Panchayat = {
  id: string;
  name: string;
  name_mr: string;
  name_hi: string;
  lat: number;
  lon: number;
  lgd_code: string | null;
  elevation_m: number | null;
  dist_river_km: number | null;
  tier: Tier;
  tier_text: string;
  days: Day[];
};

export type Block = {
  name: string;
  lat: number;
  lon: number;
  area_km2: number;
  elevation_m: number;
  gfs_cell: { lat: number; lon: number; elevation_m: number; size_deg: number };
  forecast: ({ date: string } & Record<Var, number>)[];
};

export type Forecast = {
  generated_at: string;
  stale: boolean;
  stale_since: string | null;
  served_from: string;
  source: { block_model: string; gfs_cell_elevation_m: number; validated_leads: number };
  dates: string[];
  units: Record<Var, string>;
  block: Block;
  tiers: Record<Tier, number>;
  spread: Record<Var, number>[];
  panchayats: Panchayat[];
};

type FC = GeoJSON.FeatureCollection;
export type Geo = { voronoi: FC; taluka_boundary: FC; rivers: FC };

export type Scores = { rmse: number; mae: number; bias: number };
export type Method = "block" | "physics" | "bias" | "krig" | "xgb" | "final";
export type HoldoutScores = Record<Method, Scores> & {
  spatial_pattern_rmse: Record<Method, number>;
  truth_spread_sd: number;
};

export type Validation = {
  generated_at: string;
  test_period: { start: string; end: string; days: number; rows: number };
  units: Record<Var, string>;
  methods: Method[];
  temporal: Record<Var, HoldoutScores>;
  spatial: Record<Var, HoldoutScores>;
  per_village_temporal_rmse: Record<string, Record<Var, { block: number; final: number }>>;
  verdict: Record<Var, {
    method: string;
    beats_block: boolean;
    beats_bias_corrected: boolean;
    resolves_village_differences: boolean;
  }>;
  feature_importance: Record<Var, Record<string, number>>;
  notes: string[];
};

export type Options = {
  crops: Record<string, Record<Lang, string>>;
  stages: Record<string, Record<Lang, string>>;
  langs: Record<Lang, string>;
  variables: Record<Var, { unit: string; label: string }>;
};

export type Advisory = {
  alerts: string[];
  lines: string[];
  sms: string;
  sms_chars: number;
  whatsapp: string;
  tier: Tier;
  polished?: string | null;
};

export type FeedbackSummary = {
  storage: string;
  total: number;
  accurate: number;
  accurate_pct: number | null;
  by_panchayat: Record<string, { accurate: number; not_accurate: number }>;
  by_variable: Record<string, { accurate: number; not_accurate: number }>;
  by_channel: Record<string, { accurate: number; not_accurate: number }>;
  recent: { panchayat_id: string; date: string; variable: string; rating: string; channel: string; created_at: string }[];
};
