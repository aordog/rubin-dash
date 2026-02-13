from rubin_dash.core import RubinScheduleViewer, SingleTargetPlotting, BuildDashboard

date  = '2025-09-25'
ra_t  = 350.0
dec_t = -7.0
r_ang = 2.0

rsv = RubinScheduleViewer(date, ra_t, dec_t, r_ang)
metadata = rsv.get_metadata_rsv()

print(metadata['ra'])
print(len(metadata['ra']))

target_plots = SingleTargetPlotting(date, ra_t, dec_t, r_ang, metadata)
fig_html = target_plots.visits_maps()

dash = BuildDashboard(date, ra_t, dec_t, fig_html, fig_html, fig_html, 'new_file.html')
dash.build_html()