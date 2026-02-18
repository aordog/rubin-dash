from rubin_dash.core import Target, VisitsMap, Dashboard
import time

ra_t  = 350.0
dec_t = -7.0
r_ang = 1.5
name = ' '

rsv = Target(ra_t, dec_t, r_ang, name)

for date in ['2025-09-25', '2025-09-26', '2025-09-27']:

    rsv.get_metadata_rsv(date)
    #print(rsv.data.keys())
    print(len(rsv.data[date]['ra']))
    target_plots = VisitsMap(rsv)
    fig_html = target_plots.visits_maps(date)
    dash = Dashboard(date, ra_t, dec_t, fig_html, fig_html, fig_html, 'new_file2.html')
    dash.build_html()
    time.sleep(5)
    print('')
