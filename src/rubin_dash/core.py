"""
core.py

**Author:** Anna Ordog

"""

import rubin_dash.utils as utils
import pandas as pd
import numpy as np
import psycopg2 # note: pip install psycopg2-binary
import psycopg2.extras
import json
import logging

BANDS = ('u', 'g', 'r', 'i', 'z', 'y')


class BasePlot:
    """A base class for formatting the plots."""

    def __init__(self, description: str = "Base Plot"):
        self.description = description




class QuietFilter(logging.Filter):


    """Suppress un-needed outputs to terminal/logs
    """

    NOISY = {'/check_update', '/next_update'}

    def filter(self, record):
        return not any(path in record.getMessage() for path in self.NOISY)

class Logger:
    def __init__(self, *destinations):
        self.destinations = destinations
        self.at_line_start = True

    def write(self, msg):
        self.at_line_start = utils.write(
            self.destinations, msg, self.at_line_start
        )

    def flush(self):
        for dest in self.destinations:
            dest.flush()

class TableData:
    """A class for data needed to make the table display.

    Parameters
    ----------

    """

    def __init__(self, cur, description: str = "Table data object"):
        self.description = description
        self.data = utils.populate_table(cur)

    def make_html_table(self):

        return utils.make_html_table(self.data)
    
class TargetMap:
    """A class for data needed to make the 2D map display.

    Parameters
    ----------

    """

    def __init__(self, gid, cur, description: str = "2D map object"):
        self.description = description
        self.data = utils.populate_2D_map(gid, cur)

    def make_html_visits_map(self, idx_mem, maptype):

        return utils.make_html_visits_map(self.data, idx_mem, maptype)

class TargetTimeSeries:
    """A class for data needed to make the times series display.

    Parameters
    ----------

    """

    def __init__(self, gid, idx_mem, cur, 
                 description: str = "Time series object"):
        self.description = description
        self.data = utils.populate_times_series(gid, idx_mem, cur)

    def make_html_visits_plot(self, maptype):

        return utils.make_html_visits_plot(self.data, maptype)

class ObservabilityData:
    """A class for data needed to make the future observability plot.

    Parameters
    ----------

    """

    def __init__(self, gid, idx_mem, cur, date, 
                 description: str = "Observability data object"):
        self.description = description
        self.data = utils.populate_observability(gid, idx_mem, cur, date)

    def make_html_obs_plot(self):

        return utils.make_html_obs_plot(self.data)

def initialize_tracking(user_id, file_in, declim):

    # Read in the target list:
    ra_t_list, dec_t_list = utils.read_csv_file(file_in, declim)

    print('====================================================')
    print('')
    print(f"Starting code for {len(ra_t_list)} input targets...")
    print('')

    # Group the targets from the list
    list_grouped = utils.group_targets(ra_t_list, dec_t_list, 16)

    # Open a connection to database
    conn = psycopg2.connect(dbname="lsst_database")

    # Use a DictCursor to safely specify columns later
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Check whether targets have already been loaded into this user's table
    cur.execute("SELECT COUNT(*) FROM groups WHERE user_id = %s", (user_id,))
    if cur.fetchone()[0] > 0:
        print("Targets already loaded for this user. Skipping.")
    else:
        # Load the grouped targets into the tables
        utils.setup_targets(conn, user_id, list_grouped)

    # Get the camera information
    camera = utils.get_camera()
    print('')
    print('====================================================')

    return camera, conn, cur

def populate_database(conn, cur, camera, user_id, visits, date,
                      state_lock, state):

    # Access the groups table, specifying ordering by group_id:
    cur.execute("SELECT group_id, ra_gr, dec_gr FROM groups WHERE user_id = %s ORDER BY group_id",
        (user_id,))
    rows = cur.fetchall()
    n_groups = len(rows)

    # Loop through all groups:
    for i, row in enumerate(rows):

        # Get the Rubin LSST visits for the group pointings:
        visits_use = utils.get_metadata_rsv(visits, row['ra_gr'], row['dec_gr'])

        # Calculate the masks and visits at each target:
        utils.process_group(row['group_id'], date, visits_use, camera, conn)

        with state_lock:
            state["progress"] = (i + 1) / n_groups
            state["progress_msg"] = f"UPDATING... processing group {i+1}/{n_groups}"

    return