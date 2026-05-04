"""
pipeline.py: Data-processing pipeline for rubin-dash.

This module manages the background data loop that periodically updates the
user-specific database and generates visualizations, and provides a 
frontend-agnostic API.

The module runs in a daemon thread and coordinates with the `SharedState`
object to synchronize data and display updates with the web application.

Public API
----------
- ``data_loop`` - Background driver iterating simulated dates

**Author:** Anna Ordog, for CanDIAPL
"""

from __future__ import annotations

import ctypes
import gc
import time
from typing import TYPE_CHECKING

from rubin_dash.config import (
    REFRESH_INTERVAL, 
    SIM_START, 
    SIM_END,
    SIM_LSST_DB,
    QUERY_TYPE,
)
from rubin_dash.utils import (
    simulation_dates, 
    get_base_mjd,
    date_to_nightnum,
)
from rubin_dash.database import populate_database
from rubin_dash.displays import (
    TableData,
    TargetMap,
    TargetTimeSeries,
    ObservabilityData,
)
from rubin_dash.lsst import rsv_service, sim_service

if TYPE_CHECKING:
    from rubin_dash.state import SharedState

# C-level memory reclamation:
_libc = ctypes.CDLL("libc.so.6")

def _reclaim_memory() -> None:
    """Force garbage collection and return memory to the OS.

    In long-running processes Python's garbage collector and malloc can 
    fragment memory. This function triggers garbage collection and calls libc's
    malloc_trim(0) to return freed memory pages to the OS, keeping memory usage 
    stable over extended periods.
    """
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
    """Iterate over simulated dates, updating database and state.

    This function drives the background data pipeline. It runs in a daemon 
    thread, cycling through simulated dates. In the final version, this will
    be replaced with a loop through actual dates in real time. For each cycle:

    1. Queries the Rubin Schedule Viewer (RSV) service for visits data
    2. Updates PostgreSQL database with new visits data for the user's targets
    3. Generates fresh HTML visualizations (table, figures)
    4. Atomically updates the SharedState with new data
    5. Repeats after REFRESH_INTERVAL seconds (will eventually be real days)

    State Updates
    --------
    Atomically updates SharedState fields via write() method:

    - date: ISO format date string
    - table: HTML rendering of target table
    - fig1_html: HTML of target visit map
    - fig2_html: HTML of visit time series
    - fig3_html: HTML of observability forecast
    - version: Incremented each successful update cycle
    - cycle_number: Counter tracking total cycles
    - updating: Boolean status indicator
    - progress: Numeric update progress value
    - progress_msg: Detailed progress message string

    Parameters
    ----------
    shared_state : SharedState
        Thread-safe container for dashboard state. Updated atomically via the 
        write() method and read via snapshot() method.
    conn : psycopg2.extensions.connection
        PostgreSQL database connection for reading/writing data.
    cur : psycopg2.extensions.cursor
        Database cursor object for query execution.
    camera : Camera
        Camera footprint metadata object for the observing instrument.
    user_id : int
        User identifier for filtering database queries (not relevant yet).

    Notes
    -----
    This function is designed to run as a daemon thread. The REFRESH_INTERVAL 
    is read from config.py and sets the duration between cycles. Memory is 
    explicitly reclaimed after each cycle via _reclaim_memory().
    """

    if QUERY_TYPE == 'SIM':
        base_mjd = get_base_mjd(SIM_LSST_DB)
        print(f"Querying simulated LSST data base: {SIM_LSST_DB}")
    if QUERY_TYPE == 'RSV':
        print(f"Querying Rubin Schedule Viewer")
    print('=====================================================')

    cycle_number = 0
    for date in simulation_dates(SIM_START, SIM_END):
        cycle_number += 1

        # Signal "processing"
        shared_state.write(
            cycle_number=cycle_number,
            updating=True,
            progress=0.0,
            progress_msg=f"Processing {date}...",
        )
        
        # Reading in data with simulated database option 
        if QUERY_TYPE == 'SIM':
            nightnum = date_to_nightnum(date, base_mjd)
            print(f"[CYCLE START #{cycle_number}] {date}, night #{nightnum}")
            visits = sim_service(nightnum)

        # Reading in data with RSV option    
        if QUERY_TYPE == 'RSV':
            print(f"[CYCLE START #{cycle_number}] {date}")
            visits = rsv_service(date)

        if visits.empty:
            print(f"DATA MISSING for {date}")
        else:
            populate_database(
                    conn, cur, camera, user_id, visits, date, shared_state
                )
            
            table_html = TableData(cur).make_html_table()
            fig1_html  = TargetMap(1, cur).make_html_visits_map(0, "daily")
            fig2_html  = TargetTimeSeries(1, 0, cur).make_html_visits_plot(0, "daily")
            fig3_html  = ObservabilityData(1, 0, cur, date).make_html_obs_plot()

            print(f"Table:   {len(table_html) / 1024:.1f} KB")
            print(f"Fig1:    {len(fig1_html)  / 1024:.1f} KB")
            print(f"Fig2:    {len(fig2_html)  / 1024:.1f} KB")
            print(f"Fig3:    {len(fig3_html)  / 1024:.1f} KB")

            # Atomically swap in the new data
            shared_state.write(
                date=date,
                table=table_html,
                fig1_html=fig1_html,
                fig2_html=fig2_html,
                fig3_html=fig3_html,
                version=shared_state.snapshot()["version"] + 1,
                updating=False,
                progress=0.0,
                next_update=time.time() + REFRESH_INTERVAL,
                cycle_number=cycle_number,
            )

            print("============================")
            print(f"Updated data for {date}")
            print("============================")

        _reclaim_memory()
        time.sleep(REFRESH_INTERVAL)
        print(f"[CYCLE END #{cycle_number}]")