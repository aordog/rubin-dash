from flask import Flask, jsonify, request, render_template
import webbrowser
from rubin_dash.core import Target, VisitsFigures, SummaryTable
from rubin_dash.utils import get_camera, rsv_service, read_csv_file 
from rubin_dash.utils import table_to_html, make_fake_src_list, group_targets
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# Shared state (protected by lock)
state_lock = threading.Lock()
state = {
    "date": None,
    "fig1_html": "",
    "fig2_html": "",
    "fig3_html": "",
    "table": None,
    "version": 0,
}


# Read in the target list:
ra_t_list, dec_t_list = read_csv_file('NED_result_test2.txt',0.0)
#ra_t_list, dec_t_list = make_fake_src_list(16, -20.0)

print('====================================================')
print('')
print(f"Starting code for {len(ra_t_list)} input targets...")
print('')

# Group the targets from the list
list_grouped = group_targets(ra_t_list, dec_t_list, 16)

print(f"Making Targets objects from {len(list_grouped)} groupings...")
print('')

# Make Target objects
target_set = [Target(group) for group in list_grouped]

# Get the camera information
camera = get_camera()
print('')
print('====================================================')


t_refresh = 20
# ---------- Background data loop ----------
def data_loop():

    """Runs in a daemon thread; updates shared state every t_refresh seconds."""
    start = datetime.strptime('2025-08-20', '%Y-%m-%d')
    end   = datetime.strptime('2025-11-30', '%Y-%m-%d')
    dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d')
                for i in range((end - start).days + 1)]

    for date in dates:

        ## Signal that processing has started
        with state_lock:
            state["updating"] = True

        visits = rsv_service(date)

        if visits.empty:
            print(f"DATA MISSING for {date}")
        else:

            for target in target_set:
                visits_use = target.get_metadata_rsv(visits)
                target.lsstcam_mask(visits_use, camera)
                target.count_target_visits(date)

            target_plots = VisitsFigures(target_set[0]) # DEFAULTS TO FIRST TARGET GROUP (0)
            fig1_html = target_plots.visits_maps(0, date, 'daily') # DEFAULTS TO SHOWING DAILY VISITS
            fig2_html = target_plots.visits_plots(0, 'daily') # DEFAULTS TO SHOWING DAILY VISITS
            fig3_html = target_plots.make_long_forecast_plot(0, date)
            table = SummaryTable(target_set).make_table()

            # Swap in the new data
            with state_lock:
                state["date"]     = date
                state["fig1_html"] = fig1_html
                state["fig2_html"] = fig2_html
                state["fig3_html"] = fig3_html
                state["table"]    = table
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
        fig2_html = state["fig2_html"]
        fig3_html = state["fig3_html"]
        table    = state["table"]
        version  = state["version"]
        next_update = state.get("next_update", 0)
        server_time = time.time()

    if table is None:
        return "<h2>Data loading...</h2><meta http-equiv='refresh' content='2'>"

    table_html = table_to_html(table)
    return render_template('index.html', date=date,fig1_html=fig1_html, fig2_html=fig2_html,
                           fig3_html=fig3_html,table_html=table_html, version=version,
                           countdown_seconds=max(0, next_update - server_time))

@app.route("/row_clicked", methods=["POST"])
def row_clicked():
    data = request.get_json()
    index = data["index"]
    gn = data["gn"]
    mn = data["mn"]
    maptype = data.get("maptype", "daily")
    print(f"Row {index} was clicked (maptype={maptype}, group:{gn}, member:{mn})!")

    with state_lock:
        date = state["date"]

    target_plots = VisitsFigures(target_set[int(gn)])
    fig1_html_new = target_plots.visits_maps(int(mn), date, maptype)
    fig2_html_new = target_plots.visits_plots(int(mn), maptype)
    fig3_html_new = target_plots.make_long_forecast_plot(int(mn), date)

    return jsonify({"status": "ok", "fig1_html": fig1_html_new, "fig2_html": fig2_html_new,
                    "fig3_html": fig3_html_new})

@app.route("/maptype_clicked", methods=["POST"])
def maptype_clicked():
    data = request.get_json()
    maptype = data["maptype"]
    index = data.get("index", 0)
    gn = data.get("gn",0)
    mn = data.get("mn",0)
    print(f"Map type {maptype} was clicked (table row={index}, group:{gn}, member:{mn})!")

    with state_lock:
        date = state["date"]

    target_plots = VisitsFigures(target_set[int(gn)])
    fig1_html_new = target_plots.visits_maps(int(mn), date, maptype)
    fig2_html_new = target_plots.visits_plots(int(mn), maptype)

    return jsonify({"status": "ok", "fig1_html": fig1_html_new, "fig2_html": fig2_html_new})

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
