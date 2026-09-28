"""Farmer feedback storage. SQLite by default; Postgres (e.g. Supabase free tier)
when DATABASE_URL is set. Same SQL for both, only the placeholder differs."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SQLITE_PATH = Path(os.environ.get("SQLITE_PATH", Path(__file__).resolve().parent / "cache" / "feedback.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id            {pk},
    panchayat_id  TEXT NOT NULL,
    date          TEXT NOT NULL,
    variable      TEXT NOT NULL,
    rating        TEXT NOT NULL,
    channel       TEXT NOT NULL,
    created_at    TEXT NOT NULL
)"""


class FeedbackStore:
    def __init__(self, url: str | None = None):
        self.url = url if url is not None else os.environ.get("DATABASE_URL")
        self.kind = "postgres" if self.url else "sqlite"
        self.ph = "%s" if self.url else "?"
        with self._conn() as c:
            c.cursor().execute(SCHEMA.format(pk="SERIAL PRIMARY KEY" if self.url else "INTEGER PRIMARY KEY AUTOINCREMENT"))

    def _conn(self):
        if self.url:
            import psycopg  # only needed when DATABASE_URL is set
            return psycopg.connect(self.url)
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(SQLITE_PATH)

    def add(self, panchayat_id: str, date: str, variable: str, rating: str, channel: str) -> None:
        with self._conn() as c:
            c.cursor().execute(
                f"INSERT INTO feedback (panchayat_id, date, variable, rating, channel, created_at) "
                f"VALUES ({', '.join([self.ph] * 6)})",
                (panchayat_id, date, variable, rating, channel, datetime.now(timezone.utc).isoformat(timespec="seconds")))

    def summary(self) -> dict:
        with self._conn() as c:
            cur = c.cursor()
            cur.execute("SELECT panchayat_id, variable, channel, rating, COUNT(*) FROM feedback "
                        "GROUP BY panchayat_id, variable, channel, rating")
            rows = cur.fetchall()
            cur.execute("SELECT panchayat_id, date, variable, rating, channel, created_at FROM feedback "
                        "ORDER BY id DESC LIMIT 20")
            recent = [dict(zip(("panchayat_id", "date", "variable", "rating", "channel", "created_at"), r))
                      for r in cur.fetchall()]
        total = sum(r[4] for r in rows)
        accurate = sum(r[4] for r in rows if r[3] == "accurate")

        def group(idx):
            g: dict[str, dict] = {}
            for r in rows:
                s = g.setdefault(r[idx], {"accurate": 0, "not_accurate": 0})
                s[r[3]] += r[4]
            return g

        return {"storage": self.kind, "total": total, "accurate": accurate,
                "accurate_pct": round(100 * accurate / total, 1) if total else None,
                "by_panchayat": group(0), "by_variable": group(1), "by_channel": group(2), "recent": recent}
