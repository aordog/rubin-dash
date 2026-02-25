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
    "table": None,
    "version": 0,
}

# Build the target list:
ra_t_list  = [350.0, 340.0, 330.0]
dec_t_list = [-7.0, -8.0, -7.5]
r_ang_list = [1.5, 1.5, 1.5]
name = ' '

target_set = []
for ra_t, dec_t, r_ang in zip(ra_t_list, dec_t_list, r_ang_list):
    target = Target(ra_t, dec_t, r_ang, name)
    target.add_mask_grid()
    target_set.append(target)

# ---------- Background data loop ----------
def data_loop():

    """Runs in a daemon thread; updates shared state every 10 seconds."""
    start = datetime.strptime('2025-09-25', '%Y-%m-%d')
    end   = datetime.strptime('2025-10-12', '%Y-%m-%d')
    dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d')
                for i in range((end - start).days + 1)]

    for date in dates:

        for target in target_set:
            target.get_metadata_rsv(date)
            target.lsstcam_mask(date)

        target_plots = VisitsFigures(target_set[0]) # DEFAULTS TO FIRST TARGET (0)
        fig1_html = target_plots.visits_maps(date)
        fig2_html = target_plots.visits_plots()
        table = SummaryTable(target_set).make_table()

        # Swap in the new data
        with state_lock:
            state["date"]     = date
            state["fig1_html"] = fig1_html
            state["fig2_html"] = fig2_html
            state["table"]    = table
            state["version"] += 1

        print(f"Updated data for {date}")
        time.sleep(5)
   

app = Flask(__name__)

@app.route("/")
def home():
    with state_lock:
        date     = state["date"]
        fig1_html = state["fig1_html"]
        fig2_html = state["fig2_html"]
        table    = state["table"]
        version  = state["version"]

    if table is None:
        return "<h2>Data loading...</h2><meta http-equiv='refresh' content='2'>"

    table_html = table.to_html(classes="data-table", border=0, index=False)
    return render_template('index.html', date=date,fig1_html=fig1_html, fig2_html=fig2_html,
                           table_html=table_html, version=version)

@app.route("/row_clicked", methods=["POST"])
def row_clicked():
    index = request.json["index"]
    print(f"Row {index} was clicked!")

    with state_lock:
        date = state["date"]

    target_plots = VisitsFigures(target_set[index])
    fig1_html_new = target_plots.visits_maps(date)
    fig2_html_new = target_plots.visits_plots()

    return jsonify({"status": "ok", "fig1_html": fig1_html_new, "fig2_html": fig2_html_new})

@app.route("/check_update")
def check_update():
    with state_lock:
        return jsonify({"version": state["version"]})


if __name__ == "__main__":
    data_thread = threading.Thread(target=data_loop, daemon=True)
    data_thread.start()

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(port=5000)