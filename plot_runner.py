from rubin_dash.utils import monitoring_plots

#file_time = "2026-03-30-13-53-46" # baseline bad with clicks - before fixing
#file_time = "2026-03-30-14-04-16" # baseline no clicks - before fixing
#file_time = "2026-03-30-14-59-21" # testing local versions of cur (not the issue)
#file_time = "2026-03-30-15-15-59" # test with tracemalloc results (these not shown)
#file_time = "2026-03-30-15-44-06" # memory fix implemented, but expensive diagnostic code in place
#file_time = "2026-03-30-16-00-17" # completely fixed

file_time = "2026-04-01-11-38-45" # refactor main runner into separate modules


dir_files = "/home/aordog/Dropbox/candiapl/rubin-dash-out/"

monitoring_plots(dir_files, file_time, ymax_mb=500)
