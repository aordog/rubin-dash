"""Entry point: ``python -m rubin_dash``."""

import logging
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from rubin_dash.config import (
    DEFAULT_USER_ID,
    INITIAL_OFFSET,
    MEM_TEST_MODE,
    OUTPUT_BASE,
    PORT,
    QUERY_FILE,
)
from rubin_dash.core import QuietFilter, Logger, initialize_tracking
from rubin_dash.utils import set_up_db, monitor_resources
from rubin_dash.state import SharedState
from rubin_dash.pipeline import data_loop
from rubin_dash.app import create_app
from rubin_dash.stress_monitor import stress_test_monitor

# Resolve project root (…/src/rubin_dash/__main__.py  →  …/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    # ── Output / logging ────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    run_dir = OUTPUT_BASE / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    log_file = open(run_dir / f"log_{timestamp}.txt", "w")
    sys.stdout = Logger(sys.stdout, log_file)
    sys.stderr = Logger(sys.stderr, log_file)

    # ── Database ────────────────────────────────────────────────
    set_up_db()
    logging.getLogger("werkzeug").addFilter(QuietFilter())

    camera, conn, cur = initialize_tracking(
        DEFAULT_USER_ID, QUERY_FILE, INITIAL_OFFSET,
    )

    # ── Shared state & Flask app ────────────────────────────────
    shared_state = SharedState()
    app = create_app(
        shared_state,
        conn,
        template_folder=_PROJECT_ROOT / "templates",
        static_folder=_PROJECT_ROOT / "static",
    )

    # ── Background threads ──────────────────────────────────────
    stop_monitor = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_resources,
        args=(str(run_dir / f"resources_{timestamp}.csv"), 1, stop_monitor),
        daemon=True,
    )
    monitor_thread.start()

    data_thread = threading.Thread(
        target=data_loop,
        args=(shared_state, conn, cur, camera, DEFAULT_USER_ID),
        daemon=True,
    )
    data_thread.start()

    if MEM_TEST_MODE:
        stress_test_thread = threading.Thread(
            target=stress_test_monitor,
            args=(shared_state, cur),
            daemon=True,
        )
        stress_test_thread.start()

    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    # ── Serve ───────────────────────────────────────────────────
    try:
        app.run(port=PORT)
    finally:
        stop_monitor.set()
        monitor_thread.join(timeout=10)
        log_file.close()


if __name__ == "__main__":
    main()