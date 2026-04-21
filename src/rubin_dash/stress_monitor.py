"""
Stress test monitor that prints the expected click pattern based on cycle number.
Also performs automated clicks based on cycle pattern, repeating every N seconds.
Runs as a background thread if MEM_TEST_MODE is enabled.
"""

import time
import random
from typing import TYPE_CHECKING
import requests

if TYPE_CHECKING:
    from rubin_dash.state import SharedState


def fetch_valid_rows(cur) -> list[dict]:
    """Query database to get all valid (index, gn, mn) tuples.
    
    Replicates the group/member ordering logic so that mn (mem_idx) 
    matches exactly what populate_table() computes.
    """
    cur.execute("""
        SELECT g.group_id, m.member_id
        FROM members m
        JOIN groups g ON g.group_id = m.group_id
        ORDER BY g.group_id, m.member_id
    """)
    db_rows = cur.fetchall()
    
    rows = []
    prev_gid = None
    mem_idx = 0
    for n, r in enumerate(db_rows):
        if r[0] != prev_gid:  # r[0] is group_id
            prev_gid = r[0]
            mem_idx = 0
        else:
            mem_idx += 1
        rows.append({
            "index": n,
            "gn": r[0],
            "mn": mem_idx,
        })
    return rows


def get_click_action(cycle: int) -> str:
    """Return the click action for a given cycle number (1-indexed)."""
    cycle_mod = ((cycle - 1) % 4) + 1
    if cycle_mod == 1:
        return "no clicks"
    elif cycle_mod == 2:
        return "row clicks"
    elif cycle_mod == 3:
        return "no clicks"
    elif cycle_mod == 4:
        return "map-type clicks"


def perform_row_click(base_url: str, row: dict) -> None:
    """Perform a row click on the server with the specified row."""
    try:
        payload = {
            "index": row["index"],
            "maptype": "daily",
            "gn": str(row["gn"]),
            "mn": str(row["mn"])
        }
        response = requests.post(f"{base_url}/row_clicked", json=payload, timeout=5)
    except Exception as e:
        print(f"Row click error: {e}")


def perform_maptype_click(base_url: str, maptype: str, gn: str, mn: str) -> None:
    """Perform a maptype click on the server with consistent row selection."""
    try:
        payload = {
            "index": 0,
            "maptype": maptype,
            "gn": gn,
            "mn": mn
        }
        response = requests.post(f"{base_url}/maptype_clicked", json=payload, timeout=5)
    except Exception as e:
        print(f"Maptype click error: {e}")


def stress_test_monitor(shared_state: "SharedState", cur) -> None:
    """
    Monitor cycle_number and perform automated clicks based on cycle pattern.
    
    Clicks repeat every STRESS_TEST_CLICK_INTERVAL seconds for the duration of a click cycle.
    - Row clicks (cycle 2 mod 4): random row each time (from database)
    - Maptype clicks (cycle 4 mod 4): alternate maptype, keep same row
    - No clicks (cycles 1 & 3 mod 4)
    
    Parameters
    ----------
    shared_state : SharedState
        Shared state containing cycle_number.
    cur : psycopg2 cursor
        Database cursor to fetch valid rows.
    """
    from rubin_dash.config import PORT, STRESS_TEST_CLICK_INTERVAL
    
    # Fetch valid rows once at startup
    valid_rows = fetch_valid_rows(cur)
    if not valid_rows:
        print("Warning: No valid rows available for stress testing")
        return
    
    base_url = f"http://localhost:{PORT}"
    last_cycle = 0
    current_maptype = "daily"
    fixed_row = valid_rows[0]  # Use first row for maptype clicks
    last_click_time = 0
    active_cycle = 0  # Track which cycle we're performing clicks for
    
    while True:
        snap = shared_state.snapshot()
        current_cycle = snap.get("cycle_number", 0)
        now = time.time()
        
        # When cycle changes, print the action and reset timing
        if current_cycle != last_cycle and current_cycle > 0:
            action = get_click_action(current_cycle)
            print(f"stress test for cycle {current_cycle}: {action}")
            last_cycle = current_cycle
            active_cycle = current_cycle
            last_click_time = now
        
        # Only perform clicks if we're still in the active cycle
        cycle_mod = ((active_cycle - 1) % 4) + 1 if active_cycle > 0 else 0
        
        if active_cycle > 0 and current_cycle == active_cycle and (now - last_click_time) >= STRESS_TEST_CLICK_INTERVAL:
            if cycle_mod == 2:
                # Row clicks with random row each time
                row = random.choice(valid_rows)
                perform_row_click(base_url, row)
            elif cycle_mod == 4:
                # Maptype clicks, alternating maptype but keeping same row
                current_maptype = "total" if current_maptype == "daily" else "daily"
                perform_maptype_click(base_url, current_maptype, str(fixed_row["gn"]), str(fixed_row["mn"]))
            
            last_click_time = now
        
        time.sleep(0.1)
