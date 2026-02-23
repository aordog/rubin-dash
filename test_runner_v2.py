from flask import Flask, jsonify, request, render_template
import webbrowser
from rubin_dash.core import Target, VisitsMap, Dashboard, SummaryTable
import threading

ra_t_list  = [350.0, 340.0]
dec_t_list = [-7.0, -8.0]
r_ang_list = [1.5, 1.5]
name = ' '

target_set = []

for ra_t, dec_t, r_ang in zip(ra_t_list, dec_t_list, r_ang_list):
    target_set.append(Target(ra_t, dec_t, r_ang, name))

for date in ['2025-09-25', '2025-09-26']:

    # Update all targets with current date of data:
    for target in target_set:
        target.get_metadata_rsv(date)

    target_plots = VisitsMap(target_set[0]) # NEED ABILITY TO SELECT WHICH TARGET (0 FOR NOW)
    fig_html = target_plots.visits_maps(date)

    table = SummaryTable(target_set).make_table()
    print(table)


app = Flask(__name__)

@app.route("/")
def home():
    #dash = Dashboard(date, ra_t, dec_t, fig_html, fig_html, fig_html, table, 'new_file2.html')
    #html = dash.build_html()
    table_html = table.to_html(classes="data-table", border=0, index=False)
    return render_template('index.html', date=date,fig1_html=fig_html, fig2_html=fig_html,
                           ra_t=ra_t, dec_t=dec_t, table_html=table_html)

@app.route("/row_clicked", methods=["POST"])
def row_clicked():
    index = request.json["index"]
    print(f"Row {index} was clicked!")

    target_plots = VisitsMap(target_set[index])
    fig_html_new = target_plots.visits_maps(date)

    return jsonify({"status": "ok", "fig1_html": fig_html_new})

if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(port=5000)