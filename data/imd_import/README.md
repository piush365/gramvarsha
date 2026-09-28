# Real station data (IMD AWS / ARG)

Drop CSV files here to replace the pseudo ground truth (ECMWF IFS 9 km) with real
observations. `python -m ml.build_dataset` picks up every `*.csv` in this folder.

## Format

One row per panchayat per day. Only `id` and `date` are required; include whichever
variables the station measures. Missing values: leave the cell empty.

| column | meaning | unit |
|---|---|---|
| `id`   | panchayat id from `data/panchayats.csv` (e.g. `mhaisal`) | |
| `date` | local date, `YYYY-MM-DD` | |
| `tmax` | daily maximum temperature | °C |
| `tmin` | daily minimum temperature | °C |
| `rain` | 24 h rainfall (08:30–08:30 IST as IMD reports it) | mm |
| `rh`   | daily mean relative humidity | % |
| `wind` | daily maximum wind speed at 10 m | km/h |

```csv
id,date,tmax,tmin,rain,rh,wind
mhaisal,2025-07-14,28.6,22.1,31.5,91,18.0
arag,2025-07-14,29.0,22.4,12.0,,
```

A station that is not at a village point: map it to the nearest panchayat id
(or add it to `data/panchayats.csv` + `data/terrain.csv` as its own point).

Then retrain and re-evaluate:

```bash
make retrain      # dataset -> train -> evaluate -> snapshot
```

Rows present here override the pseudo-truth for that village and day; everything
else still uses ECMWF IFS. `ml/metrics.json` will then score against the stations.
