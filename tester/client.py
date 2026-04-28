"""HTTP client wrapper for API testing.

Mesure latence, applique timeout strict, gere 1 retry avec backoff sur 429/5xx.
Ne leve jamais d'exception : retourne toujours un objet Response avec status=0
en cas d'erreur reseau / timeout.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests


DEFAULT_TIMEOUT = 5.0
DEFAULT_RETRY_BACKOFF = 1.0
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


@dataclass
class Response:
    url: str
    status: int
    latency_ms: int
    ok: bool
    headers: dict[str, str] = field(default_factory=dict)
    json_body: Any = None
    text_body: str = ""
    error: str | None = None
    attempts: int = 1


def get(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = 1,
    backoff: float = DEFAULT_RETRY_BACKOFF,
) -> Response:
    """Execute GET request avec timeout + retry sur 429/5xx.

    max_retries=1 -> 1 tentative supplementaire apres 1er echec retryable.
    Total = 1 + max_retries.
    """
    last: Response | None = None
    attempts = 0
    total_tries = 1 + max(0, max_retries)

    for i in range(total_tries):
        attempts += 1
        last = _do_request(url, params, timeout)
        last.attempts = attempts

        if last.status not in RETRYABLE_STATUSES and last.status != 0:
            return last
        if i < total_tries - 1:
            time.sleep(backoff)

    return last  # type: ignore[return-value]


def _do_request(url: str, params: dict[str, Any] | None, timeout: float) -> Response:
    started = time.perf_counter()
    try:
        r = requests.get(url, params=params, timeout=timeout)
        latency_ms = int((time.perf_counter() - started) * 1000)
        json_body: Any = None
        try:
            json_body = r.json()
        except ValueError:
            json_body = None
        return Response(
            url=r.url,
            status=r.status_code,
            latency_ms=latency_ms,
            ok=200 <= r.status_code < 300,
            headers=dict(r.headers),
            json_body=json_body,
            text_body=r.text,
        )
    except requests.Timeout:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return Response(url=url, status=0, latency_ms=latency_ms, ok=False, error="timeout")
    except requests.RequestException as e:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return Response(url=url, status=0, latency_ms=latency_ms, ok=False, error=f"network:{type(e).__name__}")
