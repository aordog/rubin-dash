"""
core.py: Core data classes and functions for Rubin Dashboard

This module provides the main data classes for managing data, plots, and 
logging within the Rubin LSST dashboard application.

**Author:** Anna Ordog, for CanDIAPL

Classes
-------
BasePlot
    Base class for plot formatting and display.
QuietFilter
    Logging filter to suppress noisy output from specific endpoints.
Logger
    Logging handler for writing to terminal and log file.
TableData
    Manages summary table data for display.
TargetMap
    Manages 2D visits coverage maps for groups of targets.
TargetTimeSeries
    Manages time series visits data for individual targets.
ObservabilityData
    Manages future observability predictions for targets.

Functions
---------
initialize_tracking
    Set up database and load target data for tracking.
populate_database
    Process visits and mask data for all target groups.
"""

import rubin_dash.utils as utils
import psycopg2 # note: pip install psycopg2-binary
import psycopg2.extras
import logging

BANDS = ('u', 'g', 'r', 'i', 'z', 'y')


class BasePlot:
    """Base class for plot objects.
    
    Provides common initialization and description tracking for plot-related
    classes. NOT YET USED!
    
    Parameters
    ----------
    description : str, optional
        Description of the plot object. Default is "Base Plot".
    
    Attributes
    ----------
    description : str
        Description of the plot object.
    """

    def __init__(self, description: str = "Base Plot"):
        self.description = description


class QuietFilter(logging.Filter):
    """Logging filter to suppress verbose Flask endpoint messages.
    
    Filters out logging records from endpoints that generate high-cadence
    messages not useful for debugging or monitoring to keep log files and 
    terminal output readable.
    
    Attributes
    ----------
    NOISY : set
        Collection of endpoint paths whose log messages should be suppressed.
    """

    NOISY = {'/check_update', '/next_update'}

    def filter(self, record):
        """Check if a log record should be allowed.
        
        Parameters
        ----------
        record : logging.LogRecord
            The log record to filter.
        
        Returns
        -------
        bool
            False if the record contains a message from a noisy endpoint,
            True otherwise.
        """
        return not any(path in record.getMessage() for path in self.NOISY)


class Logger:
    """Multi-destination logging handler with timestamp prefixing.
    
    Writes log messages to multiple output streams (terminal, file) with
    timestamps. Compatible with sys.stdout/sys.stderr redirection.
    
    Parameters
    ----------
    *destinations : file-like
        Variable number of output streams to write to (e.g., sys.stdout,
        open file objects).
    
    Attributes
    ----------
    destinations : tuple
        Collection of output streams.
    at_line_start : bool
        Flag tracking start of new line (for timestamp insertion).
    """
    
    def __init__(self, *destinations):
        self.destinations = destinations
        self.at_line_start = True

    def write(self, msg):
        """Write to all destinations with timestamp prefixing.
        
        Parameters
        ----------
        msg : str
            The message to write.
        """
        self.at_line_start = utils.write(
            self.destinations, msg, self.at_line_start
        )

    def flush(self):
        """Flush all output streams."""
        for dest in self.destinations:
            dest.flush()


class TableData:
    """Class for cumulative visits summary table data.
    
    Fetches and formats the summary table data from the database, showing
    cumulative visits counts for each target member across all filter bands.
    
    Parameters
    ----------
    cur : psycopg2.cursor
        Database cursor with DictCursor factory for safe column access.
    
    Attributes
    ----------
    data : dict
        Dictionary containing table data with visits counts per filter band
        and target coordinate information.
    """

    def __init__(self, cur, description: str = "Table data object"):
        self.description = description
        self.data = utils.populate_table(cur)

    def make_html_table(self):
        """Generate HTML table for web display.
        
        Returns
        -------
        str
            HTML string containing a formatted table with column headers
            and data rows. Debug columns hidden based on VERBOSE config.
        """
        return utils.make_html_table(self.data)
    

class TargetMap:
    """Class for 2D visit coverage maps by filter band.
    
    Fetches grid and mask data for a target group and generates 2D maps
    showing visits coverage in each of the six LSST filter bands. Displays
    daily or cumulative coverage depending on user selection.
    
    Parameters
    ----------
    gid : int
        Group ID identifying the target group.
    cur : psycopg2.cursor
        Database cursor with DictCursor factory for safe column access.
    
    Attributes
    ----------
    data : dict
        Dictionary containing map data including target group coordinates, 
        grid coordinates, group member coordinates, and mask counts by band.
    """

    def __init__(self, gid, cur, description: str = "2D map object"):
        self.description = description
        self.data = utils.populate_2D_map(gid, cur)

    def make_html_visits_map(self, idx_mem, maptype):
        """Generate 2D maps of visit coverage.
        
        Parameters
        ----------
        idx_mem : int
            Member index within the group (0-based).
        maptype : str
            Either 'daily' for today's visits or 'total' for cumulative visits.
        
        Returns
        -------
        str
            HTML string with embedded Plotly figure showing 6 heatmaps
            (one per filter band).
        """
        return utils.make_html_visits_map(self.data, idx_mem, maptype)


class TargetTimeSeries:
    """Class for time series visits progress data.
    
    Fetches historical visit data for a specific target and generates time 
    series plots showing daily or cumulative visits versus time by filter band.
    
    Parameters
    ----------
    gid : int
        Group ID identifying the target group.
    idx_mem : int
        Member index within the group (0-based).
    cur : psycopg2.cursor
        Database cursor with DictCursor factory for safe column access.

    Attributes
    ----------
    data : dict
        Dictionary containing time series data with 'daily' and 'total'
        DataFrames indexed by date with visit counts per band.
    """

    def __init__(self, gid, idx_mem, cur, 
                 description: str = "Time series object"):
        self.description = description
        self.data = utils.populate_times_series(gid, idx_mem, cur)

    def make_html_visits_plot(self, maptype):
        """Generate time series plot of visit progress.
        
        Parameters
        ----------
        maptype : str
            Either 'daily' for daily visits or 'total' for cumulative visits.
        
        Returns
        -------
        str
            HTML string with embedded Plotly figure showing line traces for
            each filter band.
        """
        return utils.make_html_visits_plot(self.data, maptype)


class ObservabilityData:
    """Class for future observability predictions.
    
    Computes and manages observability predictions for a target, including
    elevation, azimuth, and observable hours based on Vera C. Rubin 
    Observatyory location and sunrise/sunset times. Generates a plots showing: 
     - target elevation over the next N days.
     - number of observable hours over the next N days
    Note: N is currently fixed at 30 - will make this more flexible. 
    
    Parameters
    ----------
    gid : int
        Group ID identifying the target group.
    idx_mem : int
        Member index within the group (0-based).
    cur : psycopg2.cursor
        Database cursor with DictCursor factory for safe column access.
    date : str or datetime
        Reference date (typically today) for start of observability window.

    Attributes
    ----------
    data : dict
        Dictionary containing observability data including coordinates,
        time arrays, altitude/azimuth, sunrise/sunset times, and
        observable hours per day.
    """

    def __init__(self, gid, idx_mem, cur, date, 
                 description: str = "Observability data object"):
        self.description = description
        self.data = utils.populate_observability(gid, idx_mem, cur, date)

    def make_html_obs_plot(self):
        """Generate observability forecast plot.
        
        Returns
        -------
        str
            HTML string with embedded Plotly figure showing a 2-panel plot:
            top panel displays observable hours per day, bottom panel shows
            target elevation over the next 30 days with day/night shading.
        """
        return utils.make_html_obs_plot(self.data)


def initialize_tracking(user_id, file_in, declim):
    """Initialize database and load targets for tracking.
    
    Performs one-time setup of the Rubin Dashboard application by:
    - Reading the target list from a file
    - Grouping targets spatially using HEALPix
    - Establishing database connection
    - Loading target data if not already present
    - Loading LSST camera footprint information
    
    Parameters
    ----------
    user_id : int
        User ID for database queries and tracking.
    file_in : str
        Path to input file containing target RA, Dec coordinates.
        Expected to be a formatted catalog (e.g., NED query results).
    declim : float
        Declination limit in degrees. Targets with dec > declim are excluded
        from tracking. This can reduce the database size if user accidentally
        inputs targets outside of the Rubin observability range.
    
    Returns
    -------
    camera : rubin_scheduler.utils.LsstCameraFootprint
        Rubin LSST camera footprint object for computing visit masks.
    conn : psycopg2.connection
        Open database connection for lifetime of process.
    cur : psycopg2.cursor (DictCursor)
        Database cursor for queries.
    
    Raises
    ------
    psycopg2.OperationalError
        If database connection fails.
    FileNotFoundError
        If input file cannot be found.
    
    Notes
    -----
    - Targets are grouped using HEALPix nside=16
    - If targets are already loaded for this user, loading is skipped
    - LSST Camera footprint is loaded from rubin_sim_data environment
    """

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
    """Process and store visits/mask data for all target groups.
    
    Iterates through all target groups for a user and computes visits masks
    based on the Rubin Schedule Viewer data. Updates apply both daily and
    cumulative masks to the database, and updates shared state for progress
    reporting to the web interface.
    
    Parameters
    ----------
    conn : psycopg2.connection
        Database connection for reading and writing data.
    cur : psycopg2.cursor (DictCursor)
        Database cursor for queries.
    camera : rubin_scheduler.utils.LsstCameraFootprint
        Rubin LSST camera footprint object for computing visits masks.
    user_id : int
        User ID identifying which groups to process.
    visits : pandas.DataFrame
        Visit schedule data from Rubin Schedule Viewer containing ra, dec,
        execution_status, and obs_id columns.
    date : str
        Date string (YYYY-MM-DD) for which to process data.
    state_lock : threading.Lock
        Lock for thread-safe access to shared state dictionary.
    state : dict
        Shared state dictionary containing:
        - 'progress': float in [0, 1] fraction of processing complete
        - 'progress_msg': str status message for display
    
    Notes
    -----
    - Designed to run in a background thread
    - Updates shared state atomically using state_lock
    - Processes groups in database order (by group_id)
    - Each group processes its member targets and computes masks
    
    Calls
    --------
    utils.process_group : Handles individual group processing
    utils.get_metadata_rsv : Fetches visit metadata from schedule
    """

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