"""Persistance des runs en SQLite.

Schema simple : 1 table `runs`. Colonnes indexees pour le dashboard,
+ colonne `payload` qui stocke le JSON complet du run (tests detailles).

DB cree automatiquement si absente. Path = ./runs.db par defaut.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator


DB_PATH = os.environ.get("RUNS_DB_PATH", os.path.join(os.path.dirname(__file__), "runs.db"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    api             TEXT    NOT NULL,
    total           INTEGER NOT NULL,
    passed          INTEGER NOT NULL,
    failed          INTEGER NOT NULL,
    errors          INTEGER NOT NULL,
    error_rate      REAL    NOT NULL,
    availability    REAL    NOT NULL,
    latency_ms_avg  INTEGER NOT NULL,
    latency_ms_p95  INTEGER NOT NULL,
    payload         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp DESC);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


def save_run(run: dict[str, Any]) -> int:
    """Persiste un run (sortie de runner.run_all()). Retourne id insere."""
    init_db()
    s = run["summary"]
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO runs (
                timestamp, api, total, passed, failed, errors,
                error_rate, availability, latency_ms_avg, latency_ms_p95, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["timestamp"],
                run["api"],
                s["total"], s["passed"], s["failed"], s["errors"],
                s["error_rate"], s["availability"],
                s["latency_ms_avg"], s["latency_ms_p95"],
                json.dumps(run, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid or 0)


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    """Liste les derniers runs (sans payload, pour la vue tableau)."""
    init_db()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT id, timestamp, api, total, passed, failed, errors,
                   error_rate, availability, latency_ms_avg, latency_ms_p95
            FROM runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: int) -> dict[str, Any] | None:
    """Recupere un run complet (payload deserialise)."""
    init_db()
    with _conn() as c:
        row = c.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])


def latest_run() -> dict[str, Any] | None:
    """Dernier run complet."""
    init_db()
    with _conn() as c:
        row = c.execute("SELECT payload FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        return json.loads(row["payload"])


if __name__ == "__main__":
    from tester.runner import run_all
    run = run_all()
    rid = save_run(run)
    print(f"saved run id={rid}")
    print(f"total runs in db: {len(list_runs())}")
