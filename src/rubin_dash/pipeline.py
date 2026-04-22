"""
Data-processing pipeline for rubin-dash.
From Claude:
This is where the data loop and the reusable "generate plots" helper live. 
Nothing in here knows about Flask, so a future Dash / Panel / REST front-end 
can call the same functions.

Public API
----------
- ``generate_table``  — HTML table from the current DB state
- ``generate_plots``  — sky-map + time-series HTML for a (group, member)
- ``reclaim_memory``  — force Python GC + malloc_trim
- ``data_loop``       — background driver that iterates over simulated dates
"""

from __future__ import annotations

import ctypes
import gc
import time
from typing import TYPE_CHECKING

from rubin_dash.config import REFRESH_INTERVAL, simulation_dates, MEM_TEST_MODE
from rubin_dash.database import populate_database
from rubin_dash.core import (
    TableData,
    TargetMap,
    TargetTimeSeries,
    ObservabilityData,
)
from rubin_dash.utils import rsv_service

if TYPE_CHECKING:
    from rubin_dash.state import SharedState

# C-level memory reclamation:
_libc = ctypes.CDLL("libc.so.6")
def reclaim_memory() -> None:
    """Force Python GC and return freed C memory to the OS."""
    gc.collect()
    _libc.malloc_trim(0)


# The main data loop:
def data_loop(
    shared_state: SharedState,
    conn,
    cur,
    camera,
    user_id: int,
) -> None:
    """Iterate over simulated dates, updating the DB and shared state.

    Designed to run in a daemon thread.
    """
    cycle_number = 0
    for date in simulation_dates():
        cycle_number += 1
        
        print(f"[CYCLE START #{cycle_number}] {date}")

        # Signal "processing"
        shared_state.write(
            cycle_number=cycle_number,
            updating=True,
            progress=0.0,
            progress_msg=f"Processing {date}...",
        )

        visits = rsv_service(date)

        if visits.empty:
            print(f"DATA MISSING for {date}")
        else:
            # populate_database still expects (lock, dict)
            populate_database(
                conn, cur, camera, user_id, visits, date,
                shared_state.lock, shared_state.raw,
            )

            table_html = TableData(cur).make_html_table()
            fig1_html  = TargetMap(1, cur).make_html_visits_map(0, "daily")
            fig2_html  = TargetTimeSeries(1, 0, cur).make_html_visits_plot("daily")
            fig3_html  = ObservabilityData(1, 0, cur, date).make_html_obs_plot()

            print(f"Table:   {len(table_html) / 1024:.1f} KB")
            print(f"Fig1:    {len(fig1_html)  / 1024:.1f} KB")
            print(f"Fig2:    {len(fig2_html)  / 1024:.1f} KB")
            print(f"Fig3:    {len(fig3_html)  / 1024:.1f} KB")

            # Atomically swap in the new data
            with shared_state.lock:
                s = shared_state.raw
                s["date"]         = date
                s["table"]        = table_html
                s["fig1_html"]    = fig1_html
                s["fig2_html"]    = fig2_html
                s["fig3_html"]    = fig3_html
                s["version"]     += 1
                s["updating"]     = False
                s["progress"]     = 0.0
                s["next_update"]  = time.time() + REFRESH_INTERVAL
                s["cycle_number"] = cycle_number

            print("============================")
            print(f"Updated data for {date}")
            print("============================")

        reclaim_memory()
        time.sleep(REFRESH_INTERVAL)
        print(f"[CYCLE END #{cycle_number}]")