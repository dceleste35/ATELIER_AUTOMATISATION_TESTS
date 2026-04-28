"""Executeur de tests + calcul metriques QoS.

Sortie = dict JSON-serialisable, format aligne avec consignes.html :
{
  "api": "Frankfurter",
  "timestamp": "2026-04-28T09:30:00+02:00",
  "summary": {
    "total": 7, "passed": 7, "failed": 0, "errors": 0,
    "error_rate": 0.0, "availability": 1.0,
    "latency_ms_avg": 167, "latency_ms_p95": 295
  },
  "tests": [{"name": ..., "status": "PASS", "latency_ms": ..., "http_status": ..., "details": ""}, ...]
}
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .tests import ALL_TESTS, TestResult


API_NAME = "Frankfurter"


def run_all() -> dict[str, Any]:
    results: list[TestResult] = [t() for t in ALL_TESTS]
    return {
        "api": API_NAME,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "summary": _summarize(results),
        "tests": [_test_to_dict(r) for r in results],
    }


def _summarize(results: list[TestResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")

    error_rate = (failed + errors) / total if total else 0.0
    availability = (total - errors) / total if total else 0.0

    latencies = [r.latency_ms for r in results if r.status != "ERROR"]
    avg = round(sum(latencies) / len(latencies)) if latencies else 0
    p95 = _percentile(latencies, 95)

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "error_rate": round(error_rate, 3),
        "availability": round(availability, 3),
        "latency_ms_avg": avg,
        "latency_ms_p95": p95,
    }


def _percentile(values: list[int], p: float) -> int:
    """P95 par interpolation lineaire (methode classique)."""
    if not values:
        return 0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = (p / 100.0) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return round(s[lo] + (s[hi] - s[lo]) * frac)


def _test_to_dict(r: TestResult) -> dict[str, Any]:
    d = asdict(r)
    d.pop("assertions", None)
    return d


if __name__ == "__main__":
    import json
    print(json.dumps(run_all(), indent=2, ensure_ascii=False))
