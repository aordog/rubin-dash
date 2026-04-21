from rubin_dash.utils import monitoring_plots

#file_time = "2026-03-30-13-53-46" # baseline bad with clicks - before fixing
#file_time = "2026-03-30-14-04-16" # baseline no clicks - before fixing
#file_time = "2026-03-30-14-59-21" # testing local versions of cur (not the issue)
#file_time = "2026-03-30-15-15-59" # test with tracemalloc results (these not shown)
#file_time = "2026-03-30-15-44-06" # memory fix implemented, but expensive diagnostic code in place
#file_time = "2026-03-30-16-00-17" # completely fixed

#file_time = "2026-04-01-11-38-45" # refactor main runner into separate modules
#file_time = "2026-04-01-16-43-55" # simplify some functions
#file_time = "2026-04-01-16-51-09" # larger list (1420 sources)
#file_time = "2026-04-13-15-24-30"  # just checking after some major changes...
#file_time = "2026-04-15-12-53-59"  # checking with new observability plots
#file_time = "2026-04-15-19-21-40" # changes to tables and plot have made clicking slow...
#file_time = "2026-04-16-11-14-00" # further tests of new slowness
#file_time = "2026-04-16-11-26-09" # no interactions test
#file_time = "2026-04-16-11-48-23" # row diff grp, row same grp, daily/total toggle
#file_time = "2026-04-16-12-12-24" # change row order, change zoom and screen size
#file_time = "2026-04-16-13-05-24" # long run with lots of clicks
#file_time = "2026-04-16-14-48-38" # after fixing various memory issues
#file_time = "2026-04-17-11-36-33" # big data set, long-ish run during DDS meeting
#file_time = "2026-04-17-16-55-03" # test the automated stress-tester
#file_time = "2026-04-20-16-30-15" # looked like it was fixed... but wasn't
#file_time = "2026-04-21-14-45-53" # no stress control test
#file_time = "2026-04-21-15-03-03" # manual clicking
file_time = "2026-04-21-15-17-11"  # new stress test with many clicks

dir_files = "/home/aordog/Dropbox/candiapl/rubin-dash-out/"

monitoring_plots(dir_files, file_time, ymax_mb=500)
