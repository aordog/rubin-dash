from flask import Flask, jsonify, request, render_template
import webbrowser
from rubin_dash.core import Target, VisitsFigures, SummaryTable
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

# Build the target list:
ra_t_list  = [350.0, 340.0, 330.0, 180.0]#, 330.0, 325.0]
dec_t_list = [-7.0, -8.0, -7.5, -5.0]#, -8.0, -7.0]
r_ang_list = [1.5, 1.5, 1.5, 1.5]#, 1.5, 1.5]
name_list = ['Target A', 'Target B', 'Target C', 'Target D']

target_set = []
for ra_t, dec_t, r_ang, name in zip(ra_t_list, dec_t_list, r_ang_list, name_list):
    target_set.append(Target(ra_t, dec_t, r_ang, name))

t_refresh = 30

# ---------- Background data loop ----------
def data_loop():

    """Runs in a daemon thread; updates shared state every t_refresh seconds."""
    start = datetime.strptime('2025-09-25', '%Y-%m-%d')
    end   = datetime.strptime('2025-10-12', '%Y-%m-%d')
    dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d')
                for i in range((end - start).days + 1)]

    for date in dates:

        # Signal that processing has started
        with state_lock:
            state["updating"] = True

        for target in target_set:
            target.get_metadata_rsv(date)

        target_plots = VisitsFigures(target_set[0]) # DEFAULTS TO FIRST TARGET (0)
        fig1_html = target_plots.visits_maps(date, 'daily') # DEFAULTS TO SHOWING DAILY VISITS
        fig2_html = target_plots.visits_plots('daily') # DEFAULTS TO SHOWING DAILY VISITS
        fig3_html = target_plots.make_long_forecast_plot(date)
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

    table_html = table.to_html(classes="data-table", border=0, index=False)
    return render_template('index.html', date=date,fig1_html=fig1_html, fig2_html=fig2_html,
                           fig3_html=fig3_html,table_html=table_html, version=version,
                           countdown_seconds=max(0, next_update - server_time))

@app.route("/row_clicked", methods=["POST"])
def row_clicked():
    data = request.get_json()
    index = data["index"]
    maptype = data.get("maptype", "daily")
    print(f"Row {index} was clicked (maptype={maptype})!")

    with state_lock:
        date = state["date"]

    target_plots = VisitsFigures(target_set[index])
    fig1_html_new = target_plots.visits_maps(date, maptype)
    fig2_html_new = target_plots.visits_plots(maptype)
    fig3_html_new = target_plots.make_long_forecast_plot(date)

    return jsonify({"status": "ok", "fig1_html": fig1_html_new, "fig2_html": fig2_html_new,
                    "fig3_html": fig3_html_new})

@app.route("/maptype_clicked", methods=["POST"])
def maptype_clicked():

    data = request.get_json()
    maptype = data.get("maptype")
    index = data.get("index", 0)
    print(f"Map type {maptype} was clicked (table row={index})!")

    with state_lock:
        date = state["date"]

    target_plots = VisitsFigures(target_set[index])
    fig1_html_new = target_plots.visits_maps(date, maptype)
    fig2_html_new = target_plots.visits_plots(maptype)

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