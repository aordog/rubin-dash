"""
monitoring.py: code to monitor memory and CPU usage.

1. monitor_resources:
Logs resource usage for each run with or without the stress_test running.

2. stress_test: 
Stress test monitor that prints the expected click pattern based on cycle number.
Also performs automated clicks based on cycle pattern, repeating every N seconds.
Runs as a background thread if MEM_TEST_MODE is enabled.

**Author:** Anna Ordog, for CanDIAPL

"""

import time
from astropy.time import Time
from astropy.visualization import time_support
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import random
from typing import TYPE_CHECKING
import requests
import os, psutil
import numpy as np
import pandas as pd

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

def monitoring_plots(dir_files, file_time, ymax_mb=800):

    time_support()

    data = pd.read_csv(f"{dir_files}/{file_time}/resources_{file_time}.csv")

    timestamp   = Time(data['timestamp'].tolist())
    cpu_percent = np.array(data['cpu_percent'])
    memory_mb   = np.array(data['memory_mb'])

    ts_update  = read_log(dir_files, file_time, "Updated data for")
    ts_maptype = read_log(dir_files, file_time, "Map type")
    ts_rowpick = read_log(dir_files, file_time, "Row")

    fig, ax = plt.subplots(1,1, figsize=(10,5))
    ax.plot(timestamp, memory_mb, color='k', label='memory')

    colors = ['grey', 'blue', 'green']
    labels = ['update', 'toggle map', 'click row']
    linestyles = ['dashed', 'dashed', 'dotted']
    ts = [ts_update, ts_maptype, ts_rowpick]
    for j in range(0,3):
        for i in range(0,len(ts[j])):
            if i == 0:
                ax.plot(Time([ts[j][i], ts[j][i]]),[0,1000], linestyle=linestyles[j], 
                    linewidth=0.5, color=colors[j], label=labels[j])
            else:
                ax.plot(Time([ts[j][i], ts[j][i]]),[0,1000], linestyle=linestyles[j], 
                        linewidth=0.5, color=colors[j])

    ax2 = ax.twinx()
    ax2.plot(timestamp, cpu_percent, color='purple', label='CPU')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

    ax.set_ylim(0,ymax_mb)
    ax2.set_ylim(0,130)

    ax.set_xlim(timestamp[0],timestamp[-1])

    ax.legend(framealpha=1, loc='upper left')
    ax2.legend(framealpha=1, loc='upper right')

    ax.set_xlabel('Time')
    ax.set_ylabel('Memory (MB)')
    ax2.set_ylabel('CPU (%)')

    plt.savefig(f"{dir_files}/{file_time}/{file_time}.pdf")
    plt.savefig(f"{dir_files}/{file_time}/{file_time}.png")

    return

def read_log(dir_files, file_time, search_string):

    ts = []
    with open(f"{dir_files}/{file_time}/log_{file_time}.txt", 'r') as file:
        for line in file:
            if search_string in line:
                ts.append(line.strip().split()[0][1::]+" "+line.strip().split()[1][0:-1])

    return ts


def monitor_resources(log_path, interval=5, stop_event=None):
    """
    Logs CPU and memory usage to a file at regular intervals.
    Runs until stop_event is set.
    """
    process = psutil.Process(os.getpid())

    with open(log_path, "w") as f:
        f.write("timestamp,cpu_percent,memory_mb\n")

        while not stop_event.is_set():
            cpu = process.cpu_percent(interval=interval)
            mem = process.memory_info().rss / (1024 * 1024)  # bytes → MB
            ts  = time.strftime("%Y-%m-%d %H:%M:%S")

            f.write(f"{ts},{cpu:.1f},{mem:.1f}\n")
            f.flush()

def stress_test(shared_state: "SharedState", cur) -> None:
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
