"""GramVarsha API (FastAPI).

    uvicorn backend.main:app --reload --port 8000      # from the repo root

Environment variables (all optional):
    ALLOWED_ORIGINS   comma-separated extra CORS origins (localhost and *.vercel.app allowed by default)
    REFRESH_HOURS     forecast refresh interval, default 3
    DATABASE_URL      Postgres URL for feedback (default: SQLite in backend/cache/)
    GROQ_API_KEY      enables the optional LLM rewrite of advisories
    DISABLE_REFRESH   set to 1 to serve only the cached/snapshot forecast (tests, offline demos)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date as date_cls
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.advisory import advisory_for
from backend.advisory_text import CROPS, STAGES
from backend.db import FeedbackStore
from backend.forecast import ForecastService
from backend.llm import polish
from backend.tts import synthesize
from ml.features import DATA, VARIABLES
from ml.model import MODELS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("gramvarsha.api")

REFRESH_HOURS = float(os.environ.get("REFRESH_HOURS", "3"))
service: ForecastService | None = None
feedback: FeedbackStore | None = None


async def refresh_loop():
    while True:
        await asyncio.sleep(REFRESH_HOURS * 3600)
        await asyncio.to_thread(service.refresh)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service, feedback
    service = ForecastService()
    feedback = FeedbackStore()
    task = None
    if os.environ.get("DISABLE_REFRESH") == "1":
        service.load_cached()
    else:
        await asyncio.to_thread(service.refresh)
        task = asyncio.create_task(refresh_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="GramVarsha API", version="1.0", lifespan=lifespan,
              description="Block-to-panchayat weather downscaling and crop advisories (SIH26074).")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] + [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

Crop = Literal[tuple(CROPS)]
Stage = Literal[tuple(STAGES)]
Lang = Literal["en", "hi", "mr"]


def _data() -> dict:
    if not service or not service.data:
        raise HTTPException(503, "Forecast not available yet (no live data and no cached snapshot).")
    return service.data


def _panchayat(pid: str) -> dict:
    _data()
    p = service.panchayat(pid)
    if not p:
        raise HTTPException(404, f"Unknown panchayat '{pid}'")
    return p


def _meta(d: dict) -> dict:
    return {k: d.get(k) for k in ("generated_at", "stale", "stale_since", "served_from", "source", "dates", "units")}


@app.get("/api/health")
def health():
    d = service.data if service else None
    return {"ok": d is not None, "stale": d.get("stale") if d else None,
            "generated_at": d.get("generated_at") if d else None,
            "models_loaded": bool(service and service.model), "last_error": service.last_error if service else None,
            "feedback_storage": feedback.kind if feedback else None,
            "llm_enabled": bool(os.environ.get("GROQ_API_KEY"))}


@app.get("/api/block")
def block():
    d = _data()
    return {**_meta(d), "block": d["block"]}


@app.get("/api/panchayats")
def panchayats():
    d = _data()
    return {**_meta(d), "block": d["block"], "tiers": d["tiers"], "spread": d["spread"], "panchayats": d["panchayats"]}


@app.get("/api/panchayats/{pid}")
def panchayat(pid: str):
    d = _data()
    return {**_meta(d), "block": d["block"], "panchayat": _panchayat(pid)}


@app.get("/api/geo")
def geo():
    """Approximate panchayat polygons, taluka boundary and river, for the map."""
    return {name: json.loads((DATA / f"{name}.geojson").read_text()) for name in ("voronoi", "taluka_boundary", "rivers")}


@app.get("/api/advisory")
def advisory(panchayat_id: str, crop: Crop = "grapes", stage: Stage = "flowering", lang: Lang = "mr",
             polish_llm: bool = Query(True, description="use the LLM rewrite if GROQ_API_KEY is set")):
    adv = advisory_for(_panchayat(panchayat_id), crop, stage, lang)
    adv["polished"] = polish(" ".join(adv["lines"]), lang) if polish_llm else None
    adv["generated_at"] = _data()["generated_at"]
    return adv


@app.get("/api/advisory/audio")
def advisory_audio(panchayat_id: str, crop: Crop = "grapes", stage: Stage = "flowering", lang: Lang = "mr"):
    adv = advisory_for(_panchayat(panchayat_id), crop, stage, lang)
    try:
        path = synthesize(adv["voice_text"], lang)
    except Exception as e:
        log.error("TTS failed: %s", e)
        raise HTTPException(503, "Voice service unavailable right now; the text advisory still works.")
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


class Feedback(BaseModel):
    panchayat_id: str
    date: date_cls
    variable: Literal[tuple(VARIABLES) + ("overall",)] = "overall"
    rating: Literal["accurate", "not_accurate"]
    channel: Literal["web", "sms", "whatsapp", "ivr", "officer"] = "web"


class FeedbackOK(BaseModel):
    ok: bool = True
    total: int = Field(description="feedback entries stored so far")


@app.post("/api/feedback", response_model=FeedbackOK)
def post_feedback(f: Feedback):
    _panchayat(f.panchayat_id)
    feedback.add(f.panchayat_id, f.date.isoformat(), f.variable, f.rating, f.channel)
    return FeedbackOK(total=feedback.summary()["total"])


@app.get("/api/feedback/summary")
def feedback_summary():
    return feedback.summary()


@app.get("/api/validation")
def validation():
    path = MODELS_DIR.parent / "metrics.json"
    if not path.exists():
        raise HTTPException(503, "metrics.json missing -- run `python -m ml.evaluate`")
    return json.loads(path.read_text())


@app.get("/api/options")
def options():
    """Crops, stages and languages with their display names (for dropdowns)."""
    return {"crops": CROPS, "stages": STAGES, "langs": {"en": "English", "hi": "हिंदी", "mr": "मराठी"},
            "variables": {v: {"unit": u, "label": label} for v, (_, u, label) in VARIABLES.items()}}
