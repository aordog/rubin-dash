import psycopg2
import psycopg2.extras
import numpy as np
from flask import Flask, jsonify, request, render_template
import webbrowser
from rubin_dash.core import Target2, VisitsFigures, SummaryTable
from rubin_dash.utils import get_camera, rsv_service, read_csv_file, add_mask_grid, get_metadata_rsv 
from rubin_dash.utils import table_to_html, make_fake_src_list, group_targets, setup_targets, process_group, make_table_new
from rubin_dash.utils import visits_maps, load_target
import threading
import time
from datetime import datetime, timedelta


# Read in the target list:
ra_t_list, dec_t_list = read_csv_file('NED_result_test2.txt',0.0)

print('====================================================')
print('')
print(f"Starting code for {len(ra_t_list)} input targets...")
print('')

# Group the targets from the list
list_grouped = group_targets(ra_t_list, dec_t_list, 16)


# Open a connection
conn = psycopg2.connect(dbname="lsst_database")

# Use a DictCursor to safely specify columns later
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# Define this user as 1
user_id = 1

# Check whether targets have already been loaded into this user's table
cur.execute("SELECT COUNT(*) FROM groups WHERE user_id = %s", (user_id,))
if cur.fetchone()[0] > 0:
    print("Targets already loaded for this user. Skipping.")
else:
    # Load the grouped targets into the tables
    setup_targets(conn, user_id, list_grouped)

# Get the camera information
camera = get_camera()
print('')
print('====================================================')


t_refresh = 20
# ---------- Background data loop ----------

start = datetime.strptime('2025-08-20', '%Y-%m-%d')
end   = datetime.strptime('2025-11-30', '%Y-%m-%d')
dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range((end - start).days + 1)]

app = Flask(__name__)

# Shared state (protected by lock)
state_lock = threading.Lock()
state = {
    "date": None,
    "fig1_html": "",
    "table": None,
    "version": 0,
}

def data_loop():

    for date in dates:

        ## Signal that processing has started
        with state_lock:
            state["updating"] = True

        # Get the Rubin visits table for the day:
        visits = rsv_service(date)

        # Check for missing data:
        if visits.empty:
            print(f"DATA MISSING for {date}")
        else:
            # Access the groups table, specifying ordering by group_id:
            cur.execute("SELECT group_id, ra_gr, dec_gr FROM groups WHERE user_id = %s ORDER BY group_id",
                (user_id,))

            # Loop through all groups:
            for row in cur:

                # Get the Rubin LSST visits for the group pointings:
                visits_use = get_metadata_rsv(visits, row['ra_gr'], row['dec_gr'])

                # Calculate the masks and visits at each target:
                process_group(row['group_id'], date, visits_use, camera, conn)

            # New table and plots for the day:
            table = make_table_new(conn)
            target = load_target(conn, 1) #gid=1
            fig1_html = visits_maps(target, 1, 'daily') #idx_mem=1

            # Swap in the new data
            with state_lock:
                state["date"]     = date
                state["table"]    = table
                state["fig1_html"] = fig1_html
                state["version"] += 1
                state["updating"]    = False
                state["next_update"] = time.time() + t_refresh

            print('============================')
            print(f"Updated data for {date}")
            print('============================')

        time.sleep(t_refresh)


app = Flask(__name__)

@app.route("/")
def home():
    with state_lock:
        date     = state["date"]
        fig1_html = state["fig1_html"]
        table    = state["table"]
        version  = state["version"]
        next_update = state.get("next_update", 0)
        server_time = time.time()

    if table is None:
        return "<h2>Data loading...</h2><meta http-equiv='refresh' content='2'>"

    table_html = table_to_html(table)
    return render_template('index.html', date=date,fig1_html=fig1_html, 
                           table_html=table_html, version=version,
                           countdown_seconds=max(0, next_update - server_time))


@app.route("/check_update")
def check_update():
    with state_lock:
        return jsonify({"version": state["version"]})
    
@app.route("/next_update")
def next_update():
    with state_lock:
        return jsonify({
            "next_update": state.get("next_update", 0),
            "server_time": time.time(),
            "updating":    state.get("updating", False)
        })

if __name__ == "__main__":
    data_thread = threading.Thread(target=data_loop, daemon=True)
    data_thread.start()

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(port=5000)
