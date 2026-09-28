"""Tier selection, advisory rules/rendering, LLM guard and API smoke tests (offline)."""
import itertools

import pandas as pd
import pytest

from backend import forecast as fc
from backend.advisory import SMS_MAX_EN, evaluate_rules, render
from backend.advisory_text import ALERTS, CROPS, LANGS, STAGES
from backend.forecast import TierInputs, select_tier
from backend.llm import keeps_facts

CALM = {"tmax": 30, "tmin": 20, "rain": 0.5, "rh": 60, "wind": 10}


def days(**today):
    return [{**CALM, **today}, dict(CALM), dict(CALM), dict(CALM), dict(CALM)]


def codes(d, crop="sugarcane", stage="vegetative"):
    return [a.code for a in evaluate_rules(d, crop, stage)]


# ---- tier selection --------------------------------------------------------
@pytest.mark.parametrize("models,terrain,elev,tier", [
    (True, True, True, "A"),
    (False, True, True, "B"),     # models missing -> physics only
    (True, False, True, "B"),     # terrain incomplete -> physics only
    (True, False, False, "C"),    # nothing local -> pass through, flagged
    (False, False, False, "C"),
])
def test_select_tier(models, terrain, elev, tier):
    assert select_tier(TierInputs(models, terrain, elev)) == tier


# ---- advisory rules --------------------------------------------------------
def test_calm_weather_is_normal():
    assert codes(days()) == ["NORMAL"]


def test_heavy_rain_delays_spraying_and_suppresses_wind_alert():
    c = codes(days(rain=15, wind=25))
    assert "HEAVY_RAIN" in c and "WIND" not in c


def test_rain_just_below_threshold_is_not_heavy():
    assert "HEAVY_RAIN" not in codes(days(rain=14.9))


def test_dry_and_hot_means_irrigate_but_not_at_harvest():
    assert "IRRIGATE" in codes(days(rain=0, tmax=33))
    assert "IRRIGATE" not in codes(days(rain=0, tmax=33), stage="harvest")


def test_heat_stress_is_top_priority():
    assert codes(days(tmax=39, rain=0))[0] == "HEAT"


def test_wind_spray_warning():
    assert "WIND" in codes(days(wind=16))


def test_generic_fungal_only_at_flowering():
    assert "FUNGAL" in codes(days(rh=85), stage="flowering")
    assert "FUNGAL" not in codes(days(rh=85), stage="vegetative")


def test_grapes_flowering_humid_gives_downy_mildew_not_generic():
    c = codes(days(rh=82), crop="grapes", stage="flowering")
    assert "GRAPE_DOWNY" in c and "FUNGAL" not in c


def test_turmeric_heavy_rain_drainage():
    assert "TURMERIC_DRAIN" in codes(days(rain=20), crop="turmeric")


def test_harvest_rain():
    assert "HARVEST_RAIN" in codes(days(rain=6), crop="onion", stage="harvest")


def test_sowing_needs_rain():
    assert "SOWING_DRY" in codes(days(), crop="soybean", stage="sowing")


def test_tomorrows_rain_counts():
    d = days()
    d[1]["rain"] = 30
    alerts = evaluate_rules(d, "sugarcane", "vegetative")
    assert alerts[0].code == "HEAVY_RAIN" and alerts[0].params["when"] == "tomorrow"


def test_unknown_crop_rejected():
    with pytest.raises(ValueError):
        evaluate_rules(days(), "rice", "sowing")


# ---- rendering ---------------------------------------------------------------
WEATHERS = [days(), days(rain=25, wind=20), days(tmax=40, rain=0), days(rh=90, rain=3)]


def test_every_alert_has_all_languages():
    for code, text in ALERTS.items():
        assert set(text) == set(LANGS), code


@pytest.mark.parametrize("lang", LANGS)
def test_render_all_combinations(lang):
    for crop, stage, w in itertools.product(CROPS, STAGES, WEATHERS):
        out = render(evaluate_rules(w, crop, stage), w, lang, "Kavathe Piran", crop, stage, "2026-09-29")
        for key in ("sms", "whatsapp", "voice_text"):
            assert "{" not in out[key] and "}" not in out[key]
        if lang == "en":
            assert out["sms_chars"] <= SMS_MAX_EN
            assert out["sms"].isascii()        # stays a single GSM-7 SMS
        else:
            assert out["sms_chars"] <= 140


def test_voice_reads_ranges_as_words():
    out = render(evaluate_rules(days(), "wheat", "sowing"), days(), "mr", "आरग", "wheat", "sowing")
    assert "20 ते 30" in out["voice_text"] and "°" not in out["voice_text"]


# ---- LLM guard ---------------------------------------------------------------
def test_llm_rewrite_must_keep_numbers():
    rule = "Heavy rain of 18 mm expected tomorrow. Do not spray for 48 hours."
    assert keeps_facts(rule, "Expect 18 mm of rain tomorrow, so hold off spraying for 48 hours.")
    assert not keeps_facts(rule, "Expect 20 mm of rain tomorrow, so hold off spraying for 48 hours.")


# ---- pipeline + API (offline: the Open-Meteo call is replaced) ---------------
def fake_forecast(block, timeout=20):
    dates = pd.date_range("2026-07-10", periods=5).strftime("%Y-%m-%d")
    return pd.DataFrame({"date": dates, "block_tmax": 29.0, "block_tmin": 22.0, "block_rain": [0, 3, 18, 40, 1],
                         "block_rh": 85.0, "block_wind": 20.0}), 572.0


@pytest.fixture
def client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(fc, "fetch_block_forecast", fake_forecast)
    monkeypatch.setattr(fc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(fc, "CACHE_FILE", tmp_path / "forecast.json")
    monkeypatch.setattr("backend.db.SQLITE_PATH", tmp_path / "fb.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from backend.main import app
    with TestClient(app) as c:
        yield c


def test_api_end_to_end(client):
    d = client.get("/api/panchayats").json()
    assert d["stale"] is False and d["tiers"]["A"] == len(d["panchayats"]) >= 25
    p = d["panchayats"][0]
    v = p["days"][0]["values"]["tmax"]
    assert v["band"][0] <= v["value"] <= v["band"][1]
    assert "vs block" in v["explanation"]["sentence"] and v["explanation"]["parts"]
    assert all(x["values"]["rain"]["value"] >= 0 for q in d["panchayats"] for x in q["days"])

    adv = client.get(f"/api/advisory?panchayat_id={p['id']}&crop=grapes&stage=flowering&lang=mr").json()
    assert adv["alerts"][0] == "GRAPE_DOWNY"          # block RH 85 % stays humid after downscaling
    assert p["name_mr"] in adv["whatsapp"] and "द्राक्ष" in adv["whatsapp"]
    assert client.get("/api/advisory?panchayat_id=x&crop=grapes&stage=flowering&lang=mr").status_code == 404
    assert client.get(f"/api/advisory?panchayat_id={p['id']}&crop=rice").status_code == 422

    al = client.get("/api/alerts?crop=grapes&stage=flowering").json()["alerts"]
    assert set(al) == {q["id"] for q in d["panchayats"]} and all(al.values())

    r = client.post("/api/feedback", json={"panchayat_id": p["id"], "date": "2026-07-10", "rating": "not_accurate"})
    assert r.status_code == 200
    assert client.get("/api/feedback/summary").json()["total"] == 1
    assert client.get("/api/validation").json()["verdict"]["tmin"]["beats_block"] is True


def test_failed_refresh_serves_stale(client, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("Open-Meteo unreachable")
    monkeypatch.setattr(fc, "fetch_block_forecast", boom)
    from backend.main import service
    assert service.refresh() is False
    h = client.get("/api/health").json()
    assert h["ok"] and h["stale"] is True and "unreachable" in h["last_error"]
