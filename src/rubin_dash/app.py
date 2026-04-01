"""Flask application factory and route definitions."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING
import psycopg2.extras
from flask import Flask, jsonify, render_template, request
from rubin_dash.pipeline import reclaim_memory
from rubin_dash.core import TargetMap, TargetTimeSeries
if TYPE_CHECKING:
    from rubin_dash.state import SharedState


def create_app(
    shared_state: SharedState,
    conn,
    *,
    template_folder: str | Path | None = None,
    static_folder: str | Path | None = None,
) -> Flask:
    """Build and return the configured Flask application.

    Parameters
    ----------
    shared_state : SharedState
        Thread-safe state shared with the background data loop.
    conn : psycopg2 connection
        Kept open for the lifetime of the process.
    template_folder, static_folder
        Override the default Flask search paths (useful when
        ``templates/`` and ``static/`` live outside the package).
    """
    kwargs: dict = {}
    if template_folder is not None:
        kwargs["template_folder"] = str(template_folder)
    if static_folder is not None:
        kwargs["static_folder"] = str(static_folder)

    app = Flask(__name__, **kwargs)

    # helpers local to the app:
    def _render_plots(gn: int, mn: int, maptype: str):
        """Open a short-lived cursor, generate both plots, reclaim."""
        local_cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            fig1_html = TargetMap(gn, local_cur).make_html_visits_map(mn, maptype)
            fig2_html = TargetTimeSeries(gn, mn, local_cur).make_html_visits_plot(maptype)
        finally:
            local_cur.close()
        result = jsonify({"status": "ok", "fig1_html": fig1_html, "fig2_html": fig2_html})
        reclaim_memory()
        return result

    # routes:
    @app.route("/")
    def home():
        snap = shared_state.snapshot()
        if snap["table"] is None:
            return (
                "<h2>Data loading…</h2>"
                "<meta http-equiv='refresh' content='2'>"
            )
        return render_template(
            "index.html",
            date=snap["date"],
            fig1_html=snap["fig1_html"],
            fig2_html=snap["fig2_html"],
            table_html=snap["table"],
            version=snap["version"],
            countdown_seconds=max(0, snap["next_update"] - time.time()),
        )

    @app.route("/row_clicked", methods=["POST"])
    def row_clicked():
        data    = request.get_json()
        gn      = int(data["gn"])
        mn      = int(data["mn"])
        maptype = data.get("maptype", "daily")
        print(
            f"Row {data['index']} clicked "
            f"(maptype={maptype}, group:{gn}, member:{mn})"
        )
        return _render_plots(gn, mn, maptype)

    @app.route("/maptype_clicked", methods=["POST"])
    def maptype_clicked():
        data    = request.get_json()
        gn      = int(data["gn"])
        mn      = int(data["mn"])
        maptype = data["maptype"]
        print(
            f"Map type {maptype} clicked "
            f"(row={data.get('index', 0)}, group:{gn}, member:{mn})"
        )
        return _render_plots(gn, mn, maptype)

    @app.route("/check_update")
    def check_update():
        snap = shared_state.snapshot()
        return jsonify({"version": snap["version"]})

    @app.route("/next_update")
    def next_update():
        snap = shared_state.snapshot()
        return jsonify({
            "next_update":  snap["next_update"],
            "server_time":  time.time(),
            "updating":     snap["updating"],
            "progress":     snap["progress"],
            "progress_msg": snap["progress_msg"],
        })

    return app