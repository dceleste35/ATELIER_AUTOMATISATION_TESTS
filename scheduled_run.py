"""Script appele par la Scheduled Task de PythonAnywhere.

Execute un run + persiste en SQLite, sans passer par le endpoint HTTP
(donc pas soumis a l'anti-spam de /run).

Usage PA :
    python3.13 /home/<user>/<target_dir>/scheduled_run.py

Logs PA : la stdout est ecrite dans le fichier de log de la tache planifiee
(onglet Tasks de PythonAnywhere).
"""

from __future__ import annotations

import sys

from tester.runner import run_all
from storage import save_run


def main() -> int:
    run = run_all()
    rid = save_run(run)
    s = run["summary"]
    print(
        f"[scheduled] id={rid} ts={run['timestamp']} "
        f"pass={s['passed']}/{s['total']} fail={s['failed']} err={s['errors']} "
        f"avg={s['latency_ms_avg']}ms p95={s['latency_ms_p95']}ms "
        f"avail={s['availability']*100:.0f}%"
    )
    # Exit code != 0 si run dégradé → visible dans logs PA
    if s["errors"] > 0:
        return 2
    if s["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
