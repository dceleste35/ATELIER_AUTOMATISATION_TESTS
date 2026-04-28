from __future__ import annotations

import time
from threading import Lock

from flask import Flask, jsonify, redirect, render_template, request, url_for, abort

from tester.runner import run_all
from storage import save_run, list_runs, get_run, latest_run


MIN_INTERVAL_SECONDS = 30  # anti-spam : 1 run / 30s max
_last_run_at = 0.0
_run_lock = Lock()


app = Flask(__name__)


@app.get("/")
def consignes():
    return render_template("consignes.html")


@app.post("/run")
def trigger_run():
    global _last_run_at
    with _run_lock:
        now = time.time()
        wait = MIN_INTERVAL_SECONDS - (now - _last_run_at)
        if wait > 0:
            return (
                jsonify({"error": "rate_limited", "retry_after_seconds": int(wait) + 1}),
                429,
                {"Retry-After": str(int(wait) + 1)},
            )
        _last_run_at = now

    run = run_all()
    rid = save_run(run)
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"id": rid, "run": run}), 201
    return redirect(url_for("dashboard"))


@app.get("/dashboard")
def dashboard():
    last = latest_run()
    history = list_runs(limit=20)
    return render_template(
        "dashboard.html",
        last=last,
        history=history,
        min_interval=MIN_INTERVAL_SECONDS,
    )


@app.get("/runs/<int:run_id>")
def run_detail(run_id: int):
    run = get_run(run_id)
    if not run:
        abort(404)
    history = list_runs(limit=20)
    return render_template(
        "dashboard.html",
        last=run,
        history=history,
        min_interval=MIN_INTERVAL_SECONDS,
        focused_run_id=run_id,
    )


@app.get("/runs.json")
def runs_json():
    return jsonify({"runs": list_runs(limit=200)})


@app.get("/health")
def health():
    last = latest_run()
    if not last:
        return jsonify({"status": "unknown", "reason": "no_run_recorded"}), 200

    s = last["summary"]
    last_ts = last["timestamp"]
    if s["errors"] > 0:
        status = "down"
    elif s["failed"] > 0 or s["latency_ms_p95"] >= 3000:
        status = "degraded"
    else:
        status = "up"

    return jsonify({
        "status": status,
        "last_run_at": last_ts,
        "summary": s,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
