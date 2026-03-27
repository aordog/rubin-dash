from flask import Flask, jsonify, request, render_template
import webbrowser
from rubin_dash.core import initialize_tracking, populate_database
from rubin_dash.core import QuietFilter, TableData, TargetMap, TargetTimeSeries
from rubin_dash.utils import rsv_service
import threading
import time
from datetime import datetime, timedelta
import logging

###############
t_refresh = 20
user_id   = 1
###############

# Suppress un-needed outputs to terminal/logs:
logging.getLogger('werkzeug').addFilter(QuietFilter())

# Initialize the run, returning the LSST camera and 
# the DataBase connection and cursor:
camera, conn, cur = initialize_tracking(user_id, 'NED_result_test2.txt', 0.0)

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
    "fig2_html": "",
    "table": None,
    "version": 0,
}

def data_loop():

    for date in dates:

        ## Signal that processing has started
        with state_lock:
            state["updating"] = True
            state["progress"] = 0.0
            state["progress_msg"] = f"Processing {date}..."

        # Get the Rubin visits table for the day:
        visits = rsv_service(date)

        # Check for missing data:
        if visits.empty:
            print(f"DATA MISSING for {date}")
        else:
            populate_database(conn, cur, camera, user_id, visits, date,
                              state_lock, state)

            table = TableData()
            table.populate_table_cursor(cur)
            table_html = table.make_html_table()

            target = TargetMap()
            target.populate_2D_map(1, cur)
            fig1_html = target.make_html_visits_map(0, 'daily')

            timeseries = TargetTimeSeries()
            timeseries.populate_times_series(1, 0, cur) #gid=1, mem_idx=0
            fig2_html  = timeseries.make_html_visits_plot('daily')

            # Swap in the new data
            with state_lock:
                state["date"]     = date
                state["table"]    = table_html
                state["fig1_html"] = fig1_html
                state["fig2_html"] = fig2_html
                state["version"] += 1
                state["updating"]    = False
                state["progress"]    = 0.0
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
        fig2_html = state["fig2_html"]
        table_html= state["table"]
        version  = state["version"]
        next_update = state.get("next_update", 0)
        server_time = time.time()

    if table_html is None:
        return "<h2>Data loading...</h2><meta http-equiv='refresh' content='2'>"

    return render_template('index.html', date=date,fig1_html=fig1_html, 
                           fig2_html=fig2_html, table_html=table_html, version=version,
                           countdown_seconds=max(0, next_update - server_time))

@app.route("/row_clicked", methods=["POST"])
def row_clicked():
    data = request.get_json()
    index = data["index"]
    gn = data["gn"]
    mn = data["mn"]
    maptype = data.get("maptype", "daily")
    print(f"Row {index} was clicked (maptype={maptype}, group:{gn}, member:{mn})!")

    #with state_lock:
    #    date = state["date"]

    target = TargetMap()
    target.populate_2D_map(int(gn), cur)
    fig1_html_new = target.make_html_visits_map(int(mn), maptype)

    timeseries = TargetTimeSeries()
    timeseries.populate_times_series(int(gn), int(mn), cur) #gid=1, mem_idx=0
    fig2_html_new  = timeseries.make_html_visits_plot(maptype)

    return jsonify({"status": "ok", "fig1_html": fig1_html_new,
                    "fig2_html": fig2_html_new})

@app.route("/maptype_clicked", methods=["POST"])
def maptype_clicked():
    data = request.get_json()
    maptype = data["maptype"]
    index = data.get("index", 0)
    gn = data["gn"]
    mn = data["mn"]
    print(f"Map type {maptype} was clicked (table row={index}, group:{gn}, member:{mn})!")

    #with state_lock:
    #    date = state["date"]

    target = TargetMap()
    target.populate_2D_map(int(gn), cur)
    fig1_html_new = target.make_html_visits_map(int(mn), maptype)

    timeseries = TargetTimeSeries()
    timeseries.populate_times_series(int(gn), int(mn), cur) #gid=1, mem_idx=0
    fig2_html_new  = timeseries.make_html_visits_plot(maptype)

    return jsonify({"status": "ok", "fig1_html": fig1_html_new,
                    "fig2_html": fig2_html_new})


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
            "updating":    state.get("updating", False),
            "progress":     state.get("progress", 0.0),
            "progress_msg": state.get("progress_msg", ""),

        })

if __name__ == "__main__":
    data_thread = threading.Thread(target=data_loop, daemon=True)
    data_thread.start()

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(port=5000)
