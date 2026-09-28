"""Rule-based crop advisory. Deterministic, explainable, works with no API key.

    alerts = evaluate_rules(days, crop, stage)       # which rules fire, with numbers
    msg    = render(alerts, days, lang, place, crop, stage)   # SMS / WhatsApp / voice text

`days` is the downscaled forecast for one panchayat: a list (today first) of dicts
{tmax, tmin, rain, rh, wind}. Rules look at today and tomorrow (the validated
lead times); the sowing rule also looks at the 5-day rain total.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.advisory_text import (ALERTS, CROP_LINE, CROPS, DAY_LINE, DAY_NAME, HEADER, LANGS,
                                   RANGE_WORD, REPLY_LINE, SMS_SIGN, STAGES, VOICE_UNITS, WHEN)

# ---- Thresholds (all in one place so an agronomist can review them) --------
HEAVY_RAIN_MM = 15.0      # delay spraying / fertilizer 48 h
HARVEST_RAIN_MM = 5.0     # enough to spoil cut produce
DRY_RAIN_MM = 2.0         # "no meaningful rain" over today + tomorrow
IRRIGATE_TMAX_C = 33.0
HEAT_TMAX_C = 38.0
WHEAT_HEAT_TMAX_C = 34.0  # terminal heat stress in wheat
HUMID_RH = 80.0           # fungal disease threshold
WIND_KMH = 16.0           # spray drift
SOWING_DRY_5DAY_MM = 10.0
SMS_MAX_EN = 160          # one GSM-7 SMS

# Most urgent first. The SMS carries only the top one.
PRIORITY = ["HEAT", "HEAVY_RAIN", "HARVEST_RAIN", "GRAPE_DOWNY", "TURMERIC_DRAIN", "POMEGRANATE_BLIGHT",
            "WHEAT_HEAT", "JOWAR_MOULD", "FUNGAL", "IRRIGATE", "SOWING_DRY", "WIND", "NORMAL"]


@dataclass
class Alert:
    code: str
    params: dict = field(default_factory=dict)


def _r(x: float) -> int:
    """Farmers get whole numbers."""
    return int(round(x))


def evaluate_rules(days: list[dict], crop: str, stage: str) -> list[Alert]:
    if crop not in CROPS or stage not in STAGES:
        raise ValueError(f"unknown crop/stage: {crop}/{stage}")
    d0 = days[0]
    d1 = days[1] if len(days) > 1 else days[0]
    wettest, when = (d0, "today") if d0["rain"] >= d1["rain"] else (d1, "tomorrow")
    rain_2d = d0["rain"] + d1["rain"]
    rain_5d = sum(d["rain"] for d in days[:5])
    tmax = max(d0["tmax"], d1["tmax"])
    rh = max(d0["rh"], d1["rh"])
    wind = max(d0["wind"], d1["wind"])
    heavy = wettest["rain"] >= HEAVY_RAIN_MM

    a: list[Alert] = []
    if tmax >= HEAT_TMAX_C:
        a.append(Alert("HEAT", {"tmax": _r(tmax)}))
    if heavy:
        a.append(Alert("HEAVY_RAIN", {"rain": _r(wettest["rain"]), "when": when}))
    if stage == "harvest" and wettest["rain"] >= HARVEST_RAIN_MM:
        a.append(Alert("HARVEST_RAIN", {"rain": _r(wettest["rain"]), "when": when}))

    # Crop-specific nuance
    if crop == "grapes" and stage in ("vegetative", "flowering") and rh >= HUMID_RH:
        a.append(Alert("GRAPE_DOWNY"))
    if crop == "turmeric" and heavy:
        a.append(Alert("TURMERIC_DRAIN"))
    if crop == "pomegranate" and stage in ("flowering", "fruiting") and rh >= HUMID_RH and rain_2d >= DRY_RAIN_MM:
        a.append(Alert("POMEGRANATE_BLIGHT"))
    if crop == "wheat" and stage in ("flowering", "fruiting") and tmax >= WHEAT_HEAT_TMAX_C:
        a.append(Alert("WHEAT_HEAT"))
    if crop == "jowar" and stage == "fruiting" and rh >= HUMID_RH:
        a.append(Alert("JOWAR_MOULD"))

    # General rules
    crop_fungal = {"GRAPE_DOWNY", "POMEGRANATE_BLIGHT", "JOWAR_MOULD"} & {x.code for x in a}
    if stage == "flowering" and rh >= HUMID_RH and not crop_fungal:
        a.append(Alert("FUNGAL", {"rh": _r(rh)}))
    if stage != "harvest" and rain_2d <= DRY_RAIN_MM and tmax >= IRRIGATE_TMAX_C:
        a.append(Alert("IRRIGATE", {"tmax": _r(tmax), "rain": _r(rain_2d)}))
    if stage == "sowing" and rain_5d < SOWING_DRY_5DAY_MM:
        a.append(Alert("SOWING_DRY", {"rain5": _r(rain_5d)}))
    if wind >= WIND_KMH and not heavy:      # with heavy rain there is no spraying anyway
        a.append(Alert("WIND", {"wind": _r(wind)}))
    if not a:
        a.append(Alert("NORMAL"))
    return sorted(a, key=lambda x: PRIORITY.index(x.code))


def _fill(template: str, params: dict, lang: str) -> str:
    p = dict(params)
    if "when" in p:
        p["when"] = WHEN[p["when"]][lang]
    text = template.format(**p)
    return text[0].upper() + text[1:] if lang == "en" else text


def render(alerts: list[Alert], days: list[dict], lang: str, place: str, crop: str, stage: str,
           date: str = "") -> dict:
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    lines = [_fill(ALERTS[x.code][lang][0], x.params, lang) for x in alerts]

    day_lines = []
    for i, d in enumerate(days[:2]):
        day_lines.append(DAY_LINE[lang].format(day=DAY_NAME[lang][i], rain=_r(d["rain"]), tmin=_r(d["tmin"]),
                                               tmax=_r(d["tmax"]), rh=_r(d["rh"])))
    whatsapp = "\n".join([
        HEADER[lang].format(place=place, date=date), *day_lines, "",
        CROP_LINE[lang].format(crop=CROPS[crop][lang], stage=STAGES[stage][lang]),
        *[f"• {line}" for line in lines], "", REPLY_LINE[lang],
    ])

    # SMS: place + most urgent short line + today's key numbers, trimmed to fit.
    top = _fill(ALERTS[alerts[0].code][lang][1], alerts[0].params, lang)
    d0 = days[0]
    nums = {"en": f" Today {_r(d0['rain'])}mm, {_r(d0['tmax'])}C.",
            "hi": f" आज {_r(d0['rain'])}मिमी, {_r(d0['tmax'])}°से.",
            "mr": f" आज {_r(d0['rain'])}मिमी, {_r(d0['tmax'])}°से."}[lang]
    candidates = [f"{place}: {top}.{nums}{SMS_SIGN[lang]}", f"{place}: {top}.{nums}", f"{place}: {top}."]
    # Devanagari needs Unicode SMS (70 chars/part); keep it as short as the English cap allows.
    limit = SMS_MAX_EN if lang == "en" else 140
    sms = next((c for c in candidates if len(c) <= limit), candidates[-1][:limit])

    # Voice: full stops between parts (pauses), "22-31" read as "22 to 31", units spelt out.
    voice = " ".join(s.rstrip(".") + "." for s in [place, *day_lines, *lines])
    voice = re.sub(r"(\d+)-(\d+)", r"\1 " + RANGE_WORD[lang] + r" \2", voice)
    for a, b in VOICE_UNITS[lang]:
        voice = voice.replace(a, b)

    return {"lang": lang, "alerts": [x.code for x in alerts], "params": [x.params for x in alerts],
            "lines": lines, "sms": sms, "sms_chars": len(sms), "whatsapp": whatsapp, "voice_text": voice}


def advisory_for(panchayat: dict, crop: str, stage: str, lang: str) -> dict:
    """Convenience: build from a panchayat record produced by backend.forecast."""
    days = [{v: d["values"][v]["value"] for v in ("tmax", "tmin", "rain", "rh", "wind")} for d in panchayat["days"]]
    place = {"en": panchayat["name"], "hi": panchayat["name_hi"], "mr": panchayat["name_mr"]}[lang]
    alerts = evaluate_rules(days, crop, stage)
    out = render(alerts, days, lang, place, crop, stage, date=panchayat["days"][0]["date"])
    out.update({"panchayat_id": panchayat["id"], "crop": crop, "stage": stage, "tier": panchayat["tier"]})
    return out
