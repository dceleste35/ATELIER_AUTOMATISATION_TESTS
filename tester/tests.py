"""Tests "as code" pour l'API Frankfurter.

Chaque test = fonction qui retourne un TestResult.
Convention :
- status = "PASS" si toutes les assertions passent
- status = "FAIL" si assertion metier echoue (API a repondu mais pas comme attendu)
- status = "ERROR" si erreur reseau / timeout (status=0 dans la Response)

latency_ms = latence de l'appel HTTP, sert au calcul QoS dans runner.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .client import get


BASE_URL = "https://api.frankfurter.app"


@dataclass
class TestResult:
    name: str
    status: str  # "PASS" | "FAIL" | "ERROR"
    latency_ms: int
    http_status: int = 0
    details: str = ""
    assertions: list[str] = field(default_factory=list)


def _check(cond: bool, msg: str, fails: list[str]) -> None:
    if not cond:
        fails.append(msg)


def _wrap_response(name: str, r) -> TestResult | None:
    """Retourne TestResult ERROR si pas de reponse HTTP, sinon None."""
    if r.status == 0:
        return TestResult(
            name=name, status="ERROR", latency_ms=r.latency_ms,
            http_status=0, details=f"no HTTP response: {r.error}",
        )
    return None


# ---------- Tests "Contrat" ----------

def test_latest_eur_contract() -> TestResult:
    """GET /latest?from=EUR -> 200 + champs amount/base/date/rates valides."""
    name = "GET /latest?from=EUR (contract)"
    r = get(f"{BASE_URL}/latest", {"from": "EUR"})
    err = _wrap_response(name, r)
    if err:
        return err

    fails: list[str] = []
    _check(r.status == 200, f"status {r.status} != 200", fails)
    _check(isinstance(r.json_body, dict), "body not a dict", fails)
    body = r.json_body or {}
    _check("amount" in body and isinstance(body.get("amount"), (int, float)), "missing/invalid amount", fails)
    _check(body.get("base") == "EUR", f"base != 'EUR' (got {body.get('base')!r})", fails)
    _check(isinstance(body.get("date"), str) and len(body.get("date", "")) == 10, "date not YYYY-MM-DD", fails)
    rates = body.get("rates")
    _check(isinstance(rates, dict) and len(rates) > 0, "rates empty or not dict", fails)
    if isinstance(rates, dict):
        bad_types = [k for k, v in rates.items() if not isinstance(v, (int, float))]
        _check(len(bad_types) == 0, f"non-numeric rates: {bad_types[:3]}", fails)

    return TestResult(
        name=name,
        status="PASS" if not fails else "FAIL",
        latency_ms=r.latency_ms,
        http_status=r.status,
        details="; ".join(fails),
    )


def test_latest_eur_to_usd() -> TestResult:
    """GET /latest?from=EUR&to=USD -> rates ne contient que USD."""
    name = "GET /latest?from=EUR&to=USD (filter)"
    r = get(f"{BASE_URL}/latest", {"from": "EUR", "to": "USD"})
    err = _wrap_response(name, r)
    if err:
        return err

    fails: list[str] = []
    _check(r.status == 200, f"status {r.status} != 200", fails)
    rates = (r.json_body or {}).get("rates", {})
    _check(isinstance(rates, dict), "rates not a dict", fails)
    _check(list(rates.keys()) == ["USD"], f"rates keys != ['USD'] (got {list(rates.keys())})", fails)
    if rates.get("USD") is not None:
        _check(rates["USD"] > 0, f"USD rate not positive: {rates['USD']}", fails)

    return TestResult(
        name=name,
        status="PASS" if not fails else "FAIL",
        latency_ms=r.latency_ms,
        http_status=r.status,
        details="; ".join(fails),
    )


def test_currencies_list() -> TestResult:
    """GET /currencies -> dict {ISO4217: nom}, >=30 entrees."""
    name = "GET /currencies (list)"
    r = get(f"{BASE_URL}/currencies")
    err = _wrap_response(name, r)
    if err:
        return err

    fails: list[str] = []
    _check(r.status == 200, f"status {r.status} != 200", fails)
    body = r.json_body or {}
    _check(isinstance(body, dict), "body not a dict", fails)
    _check(len(body) >= 30, f"only {len(body)} currencies (<30)", fails)
    bad_codes = [k for k in body if not (isinstance(k, str) and len(k) == 3 and k.isupper() and k.isalpha())]
    _check(len(bad_codes) == 0, f"invalid codes: {bad_codes[:3]}", fails)
    _check("EUR" in body and "USD" in body, "EUR or USD missing", fails)

    return TestResult(
        name=name,
        status="PASS" if not fails else "FAIL",
        latency_ms=r.latency_ms,
        http_status=r.status,
        details="; ".join(fails),
    )


def test_historical_date() -> TestResult:
    """GET /2024-01-02?from=EUR -> date historique, meme schema que /latest."""
    name = "GET /2024-01-02?from=EUR (historical)"
    r = get(f"{BASE_URL}/2024-01-02", {"from": "EUR"})
    err = _wrap_response(name, r)
    if err:
        return err

    fails: list[str] = []
    _check(r.status == 200, f"status {r.status} != 200", fails)
    body = r.json_body or {}
    _check(body.get("base") == "EUR", f"base != 'EUR' (got {body.get('base')!r})", fails)
    date = body.get("date", "")
    _check(isinstance(date, str) and date.startswith("2024-01"), f"date not in 2024-01: {date!r}", fails)
    _check(isinstance(body.get("rates"), dict) and len(body.get("rates", {})) > 0, "rates empty", fails)

    return TestResult(
        name=name,
        status="PASS" if not fails else "FAIL",
        latency_ms=r.latency_ms,
        http_status=r.status,
        details="; ".join(fails),
    )


def test_invalid_currency() -> TestResult:
    """GET /latest?from=ZZZ -> 404 ou 422 (devise inexistante)."""
    name = "GET /latest?from=ZZZ (invalid input)"
    r = get(f"{BASE_URL}/latest", {"from": "ZZZ"}, max_retries=0)
    err = _wrap_response(name, r)
    if err:
        return err

    fails: list[str] = []
    _check(r.status in (404, 422), f"status {r.status} not in (404, 422)", fails)

    return TestResult(
        name=name,
        status="PASS" if not fails else "FAIL",
        latency_ms=r.latency_ms,
        http_status=r.status,
        details="; ".join(fails),
    )


def test_content_type_json() -> TestResult:
    """GET /latest -> Content-Type contient application/json."""
    name = "GET /latest (Content-Type JSON)"
    r = get(f"{BASE_URL}/latest")
    err = _wrap_response(name, r)
    if err:
        return err

    fails: list[str] = []
    ctype = r.headers.get("Content-Type", "")
    _check("application/json" in ctype.lower(), f"Content-Type='{ctype}'", fails)

    return TestResult(
        name=name,
        status="PASS" if not fails else "FAIL",
        latency_ms=r.latency_ms,
        http_status=r.status,
        details="; ".join(fails),
    )


# ---------- Test "Robustesse / QoS" ----------

def test_latency_threshold() -> TestResult:
    """GET /latest -> latence < 3000 ms (seuil QoS atelier)."""
    name = "GET /latest (latency < 3000ms)"
    r = get(f"{BASE_URL}/latest")
    err = _wrap_response(name, r)
    if err:
        return err

    fails: list[str] = []
    _check(r.latency_ms < 3000, f"latency {r.latency_ms}ms >= 3000ms", fails)

    return TestResult(
        name=name,
        status="PASS" if not fails else "FAIL",
        latency_ms=r.latency_ms,
        http_status=r.status,
        details="; ".join(fails),
    )


# ---------- Registre ----------

ALL_TESTS: list[Callable[[], TestResult]] = [
    test_latest_eur_contract,
    test_latest_eur_to_usd,
    test_currencies_list,
    test_historical_date,
    test_invalid_currency,
    test_content_type_json,
    test_latency_threshold,
]
