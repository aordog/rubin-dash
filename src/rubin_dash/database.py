"""
database.py: User-specific Database setup and population for target tracking.

This module manages all database operations for the dashboard, including 
schema creation for the user-specific database, initialization of the database
with target organization, and populating the database with daily updates.

Public API
----------
- ``set_up_db`` - Create and initialize the database schema.
- ``initialize_tracking`` - Load and organize targets and setup for a user.
- ``populate_database`` - Process visits and mask data for all groups.

**Author:** Anna Ordog, for CanDIAPL
"""

import pandas as pd
import healpy as hp
import numpy as np
import psycopg2
from rubin_dash.utils import remove_high_dec # WILL GET RID OF THIS!
from rubin_dash.lsst import get_camera, get_metadata_rsv
import subprocess
from rubin_dash.config import DB_NAME

BANDS = ('u', 'g', 'r', 'i', 'z', 'y')
MASK_COLS = [f'{b}mask' for b in BANDS]
VISIT_COLS = [f'{b}visits' for b in BANDS]


def _read_csv_file(file_in, declim):
    """Read target catalog from CSV file with declination filtering.

    Parses a formatted catalog file (e.g., NED query results) and extracts 
    RA and Dec coordinates, limiting targets to the LSST declination limit
    defined by INITIAL_OFFSET in config.py to discard targets the user may
    have included that will not be observable.
    TO DO: include warning for user stating not all their sources are being
    tracked.

    Parameters
    ----------
    file_in : str
        Path to input catalog file with pipe-delimited format.
        TO DO: make this more flexible!
    declim : float
        Declination limit in degrees. Targets with dec > declim are
        excluded from the returned list.

    Returns
    -------
    tuple of np.ndarray
        (ra_list, dec_list) — Arrays of RA and Dec coordinates (degrees).
    """

    with open(file_in, 'r') as f:
        lines = f.readlines()

    header_idx = next(i for i, line in enumerate(lines) if line.startswith('No.'))

    df = pd.read_csv(file_in,
                    sep='|',
                    skiprows=header_idx,
                    header=0,
                    skipinitialspace=True)

    df.columns = df.columns.str.strip()
    df['Object Name'] = df['Object Name'].str.strip()

    return remove_high_dec(df['RA'].values.astype(float), 
                           df['DEC'].values.astype(float), declim)

def _group_targets(ra_list, dec_list, nside):
    """Group targets spatially using HEALPix grid.

    Organizes targets into spatial groups based on HEALPix tessellation. 
    Each group corresponds to a HEALPix pixel and contains all targets 
    falling within that pixel.

    Parameters
    ----------
    ra_list : np.ndarray
        Array of right ascension values (degrees).
    dec_list : np.ndarray
        Array of declination values (degrees).
    nside : int
        HEALPix nside parameter controlling pixel/grouping size.

    Returns
    -------
    list of dict
        Each dict contains:
        - 'name_gr': Group identifier string
        - 'ra_gr', 'dec_gr': Group center coordinates
        - 'ra_mem', 'dec_mem': Arrays of member target coordinates
    """

    pixel_ids = hp.ang2pix(nside, ra_list, dec_list, lonlat=True)
    idx_filled = np.unique(pixel_ids)

    groups = []
    for idx in idx_filled:
        coords_group = hp.pix2ang(nside, idx, lonlat=True)
        group_dict = {'name_gr': 'nside'+str(nside)+'_'+str(idx),
                      'ra_gr'  : float(coords_group[0]),
                      'dec_gr' : float(coords_group[1]),
                      'ra_mem' : ra_list[pixel_ids == idx],
                      'dec_mem': dec_list[pixel_ids == idx]}
        groups.append(group_dict)

    return groups

def _setup_targets(conn, user_id, list_grouped):
    """Populate database with target groups and members.

    Inserts target group data and individual target members into the 'groups' 
    and 'members' database tables. Creates spatial grids for each group 
    using _add_mask_grid(), which are used in 2D visits map computations.

    Parameters
    ----------
    conn : psycopg2.connection
        Database connection for insert operations.
    user_id : int
        User ID to associate with all target groups.
    list_grouped : list of dict
        List of grouped targets from _group_targets().
    """

    cur = conn.cursor()

    for group in list_grouped:

        # Make the grids centred on each group for the masks:
        ra_grid, dec_grid = _add_mask_grid(
            group['ra_gr'], group['dec_gr']
        )

        # Add group info to the 'groups' table, returning the group ID:
        cur.execute("""
            INSERT INTO groups (user_id, name_gr, ra_gr, dec_gr, ra_grid, dec_grid)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING group_id
        """, (user_id, group['name_gr'], group['ra_gr'], group['dec_gr'],
              psycopg2.Binary(ra_grid.tobytes()),
              psycopg2.Binary(dec_grid.tobytes())))
        
        # Extract group ID to use in 'members' table:
        gid = cur.fetchone()[0]

        # For each group, add all the member-target info to the 'members' group
        for idx, (ra_mem, dec_mem) in enumerate(zip(group['ra_mem'], group['dec_mem'])):
            cur.execute("""
                INSERT INTO members (group_id, member_idx, ra_mem, dec_mem)
                VALUES (%s, %s, %s, %s)
            """, (gid, idx, float(ra_mem), float(dec_mem)))

    # Save everything to the database:
    conn.commit()

    return

def _add_mask_grid(pointing_ra, pointing_dec):
    """Create a spatial grid for 2D visits map computation for each group.

    Generates a regular grid of RA/Dec coordinates centered on a group's 
    pointing position. Grid spacing is 1 arcminute with a 2.5-degree radius, 
    suitable for nside=16 grouping.
    TO DO: look into flexibility around this!

    Parameters
    ----------
    pointing_ra : float
        RA of group center (degrees).
    pointing_dec : float
        Dec of group center (degrees).

    Returns
    -------
    tuple of np.ndarray
        (ra_grid, dec_grid) - Flattened arrays of grid coordinates.
    """

    samp=0.0166667
    radius = 2.5 # should work well for nside=16 grouping

    ra_grid = np.arange(pointing_ra - radius*np.cos(np.radians(pointing_dec)), 
                   pointing_ra + radius, 
                   samp * np.cos(np.radians(pointing_dec)))
    
    dec_grid = np.arange(pointing_dec - radius*np.cos(np.radians(pointing_dec)), 
                    pointing_dec + radius, 
                    samp)
    
    ra_grid, dec_grid = np.meshgrid(ra_grid, dec_grid)
    ra_grid  = ra_grid.flatten()
    dec_grid = dec_grid.flatten()

    return ra_grid, dec_grid

def _compute_daily_masks(visits_use, camera, ra_grid, dec_grid):
    """Compute visit masks for all bands/filters on the spatial grid.

    For each band, counts how many visits from the latest observations 
    occurred at each grid point using the LSST camera footprint.

    Parameters
    ----------
    visits_use : dict
        Visit data with keys: 'ra', 'dec', 'band', 'rot'
    camera : rubin_scheduler.utils.LsstCameraFootprint
        Camera footprint object for mask calculations.
    ra_grid : np.ndarray
        RA coordinates of grid points (degrees).
    dec_grid : np.ndarray
        Dec coordinates of grid points (degrees).

    Returns
    -------
    dict
        Keys are mask column names; values are visit count arrays.
    """

    latest = {}

    for band, mask_name in zip(BANDS, MASK_COLS):

        latest[mask_name] = np.zeros(len(ra_grid))

        idxs = np.where(np.array(visits_use['band']) == band)[0]
        for i in idxs:
           idx_visit = camera(ra_grid, dec_grid, 
                              visits_use['ra'][i], 
                              visits_use['dec'][i], 
                              visits_use['rot'][i])
           latest[mask_name][idx_visit] = latest[mask_name][idx_visit] + 1

    return latest

def _insert_daily_visits(cur, date, member_id, v):
    """Insert daily visit counts for a member into the database.

    Stores visit count data for one target member on a specific date
    into the member_daily_visits table.

    Parameters
    ----------
    cur : psycopg2.cursor
        Database cursor for executing the insert.
    date : str
        Date string (YYYY-MM-DD) for the observations.
    member_id : int
        Database ID of the target member.
    v : dict
        Visit counts dictionary with keys for each band.
    """
    cols = ', '.join(VISIT_COLS)
    phs  = ', '.join(['%s'] * len(VISIT_COLS))

    cur.execute(f"""
        INSERT INTO member_daily_visits
               (time, member_id, {cols})
        VALUES (%s, %s, {phs})
    """, (date, member_id, *[v[b] for b in VISIT_COLS]))

def _insert_member_totals(cur, date, member_id, v):
    """Insert cumulative visit counts for a member into the database.

    Stores cumulative (total) visit count data for one target member
    into the member_totals table.

    Parameters
    ----------
    cur : psycopg2.cursor
        Database cursor for executing the insert.
    date : str
        Date string (YYYY-MM-DD) for the observations.
    member_id : int
        Database ID of the target member.
    v : dict
        Visit counts dictionary with keys for each band.
    """
    cols = ', '.join(VISIT_COLS)
    phs  = ', '.join(['%s'] * len(VISIT_COLS))

    cur.execute(f"""
        INSERT INTO member_totals
               (time, member_id, {cols})
        VALUES (%s, %s, {phs})
    """, (date, member_id, *[v[b] for b in VISIT_COLS]))

def _upsert_masks(cur, gid, mask_type, masks):
    """Insert or update mask data for a group in the database.

    Inserts new mask data or updates existing masks for a group. Handles 
    both daily ('latest') and cumulative ('total') mask types. If the masks
    already exist in the database from previous days, they are overwritten
    (ON CONFLICT). While a time series of daily visits for each target is
    stored (_insert_daily_visits and _insert_member_totals), the 2D masks 
    stored for total and daily are ONLY the latest.

    Parameters
    ----------
    cur : psycopg2.cursor
        Database cursor for executing the upsert.
    gid : int
        Group ID for which to store masks.
    mask_type : str
        Type of mask being stored: 'latest' for daily or 'total' for 
        cumulative.
    masks : dict
        Mask data dictionary with arrays for each band.
    """
    cols = ', '.join(MASK_COLS)
    phs  = ', '.join(['%s'] * len(MASK_COLS))
    sets = ', '.join(f"{c} = EXCLUDED.{c}" for c in MASK_COLS)

    cur.execute(f"""
        INSERT INTO group_masks
               (group_id, mask_type, updated_at, {cols})
        VALUES (%s, %s, NOW(), {phs})
        ON CONFLICT (group_id, mask_type) DO UPDATE SET
            updated_at = NOW(),
            {sets}
    """, (gid, mask_type,
          *[psycopg2.Binary(masks[col].astype(np.int16).tobytes()) for col in MASK_COLS]))

def _compute_visits(ra_mem, dec_mem, ra_grid, dec_grid, mask):
    """Count visits for a group member target from a mask grid.

    Finds the closest mask grid point to a target member and returns
    the visit counts for that grid point across all bands.

    Parameters
    ----------
    ra_mem : float
        Member target RA (degrees).
    dec_mem : float
        Member target Dec (degrees).
    ra_grid : np.ndarray
        RA coordinates of grid points (degrees).
    dec_grid : np.ndarray
        Dec coordinates of grid points (degrees).
    mask : dict
        Mask dictionary with visit count arrays for each band.

    Returns
    -------
    dict
        Visit counts for each band at the nearest grid point.
    """

    visits_counts = {}

    dist = np.sqrt((ra_mem-ra_grid)**2 + ((dec_mem-dec_grid)*np.cos(dec_mem*np.pi/180.))**2)
    idx = dist.argmin()

    for listname, maskname in zip(VISIT_COLS, MASK_COLS):
        visits_counts[listname] = float(mask[maskname][idx])

    return visits_counts

def _process_group(gid, date, visits, camera, conn):
    """Process one group: compute masks and update database.

    Loads a group's spatial grid and existing cumulative masks from the
    database using _read_grid_and_mask(), computes new daily masks from
    visit data using _compute_daily_masks(), accumulates into totals, and
    saves both to the database using _upsert_masks(). Also computes and
    saves visit counts for each member target using _compute_visits(),
    _insert_member_totals(), and _insert_daily_visits().

    Parameters
    ----------
    gid : int
        Group ID to process.
    date : str
        Date string (YYYY-MM-DD) for the observation epoch.
    visits : dict
        Visit data with keys: 'ra', 'dec', 'band', 'rot'
    camera : rubin_scheduler.utils.LsstCameraFootprint
        Camera footprint for mask computation.
    conn : psycopg2.connection
        Database connection for loading and saving data.
    """

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    ra_grid, dec_grid, mask_row = _read_grid_and_mask(gid, cur)

    if mask_row and mask_row[MASK_COLS[0]] is not None:
        totals = {col: np.frombuffer(mask_row[col], dtype=np.int16).copy() for col in MASK_COLS}
    else:
        totals = {col: np.zeros(len(ra_grid), dtype=np.int16) for col in MASK_COLS}

    # Compute today's masks:
    latest = _compute_daily_masks(
        visits, camera, ra_grid, dec_grid
    )
    latest = {col: latest[col].astype(np.int16) for col in MASK_COLS}

    # Add today's mask to the totals:
    for col in MASK_COLS:
        totals[col] += latest[col]

    # Save both mask sets
    _upsert_masks(cur, gid, 'latest', latest)
    _upsert_masks(cur, gid, 'total',  totals)

    # Load members for the selected group:
    cur.execute("""
                SELECT member_id, ra_mem, dec_mem FROM members
                WHERE group_id = %s ORDER BY member_idx
                """, (gid,))
    
    # Compute total and daily visits:
    for mem in cur.fetchall():
        total_v = _compute_visits(
            mem['ra_mem'], mem['dec_mem'],
            ra_grid, dec_grid, totals
        )
        daily_v = _compute_visits(
            mem['ra_mem'], mem['dec_mem'],
            ra_grid, dec_grid, latest
        )
        
        # Save daily and total visits
        _insert_member_totals(cur, date, mem['member_id'], total_v)
        _insert_daily_visits(cur, date, mem['member_id'], daily_v)

    conn.commit()
    
    return

def _read_grid_and_mask(gid, cur):
    """Load spatial grid and masks for a group from database.

    Retrieves the pre-computed spatial grid for a group and loads the
    existing cumulative mask (or None if first observation).

    Parameters
    ----------
    gid : int
        Group ID to load data for.
    cur : psycopg2.cursor (DictCursor)
        Database cursor for queries.

    Returns
    -------
    tuple
        (ra_grid, dec_grid, mask_row) where grid arrays are 1D numpy
        arrays and mask_row is a cursor row or None.
    """

    # Load grids needed for making the mask:
    cur.execute(
            "SELECT ra_gr, dec_gr, ra_grid, dec_grid FROM groups WHERE group_id = %s",
            (gid,))
    grp = cur.fetchone()
    ra_grid  = np.frombuffer(grp['ra_grid'])
    dec_grid = np.frombuffer(grp['dec_grid'])

    # Load existing total masks (zeros on first day):
    cols = ', '.join(MASK_COLS)
    cur.execute(f"""
                SELECT {cols}
                FROM group_masks WHERE group_id = %s AND mask_type = 'total'
                """, (gid,))
    mask_row = cur.fetchone()

    return ra_grid, dec_grid, mask_row


def set_up_db():
    """Create and initialize the database schema for the user-specific table.

    Drops any existing database with the name specified in config, creates a 
    new one, and loads the schema from schema.sql.

    Notes
    -----
    This is a destructive operation. Use only for initialization.
    TO DO: for now this is being removed each time for a fresh start each time
    during testing. Will need to revisit how this is handled for final version.
    """
    subprocess.run(["dropdb", DB_NAME])
    subprocess.run(["createdb", DB_NAME])
    subprocess.run(["psql", "-d", DB_NAME, "-f", "schema.sql"])
    return


def initialize_tracking(user_id, file_in, declim):
    """Initialize user-specific database and load targets for tracking.
    
    Performs one-time setup of the Rubin Dashboard application by:
    - Reading the target list from a file using _read_csv_file()
    - Grouping targets spatially using _group_targets()
    - Establishing database connection
    - Loading target data if not already present using _setup_targets()
    - Loading LSST camera footprint information
    
    Parameters
    ----------
    user_id : int
        User ID for database queries and tracking.
    file_in : str
        Path to input file containing target RA, Dec coordinates.
        Expected to be a formatted catalog (e.g., NED query results).
    declim : float
        Declination limit in degrees. Targets with dec > declim are
        excluded from tracking. This can reduce the database size if
        user accidentally inputs targets outside of the Rubin
        observability range.
    
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
    ra_t_list, dec_t_list = _read_csv_file(file_in, declim)

    print('====================================================')
    print('')
    print(f"Starting code for {len(ra_t_list)} input targets...")
    print('')

    # Group the targets from the list
    list_grouped = _group_targets(ra_t_list, dec_t_list, 16)

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
        _setup_targets(conn, user_id, list_grouped)

    # Get the camera information
    camera = get_camera()
    print('')
    print('====================================================')

    return camera, conn, cur


def populate_database(conn, cur, camera, user_id, visits, date, shared_state):
    """Process and store visits/mask data for all target groups.

    Iterates through all target groups for a user and computes 2D visit
    masks based on the Rubin Schedule Viewer data using _process_group().
    Updates both daily and cumulative masks in the user-specific database,
    and updates shared state for progress reporting to the web interface.

    Parameters
    ----------
    conn : psycopg2.connection
        Database connection for reading and writing data.
    cur : psycopg2.cursor (DictCursor)
        Database cursor for queries.
    camera : rubin_scheduler.utils.LsstCameraFootprint
        Rubin LSST camera footprint object for computing visit masks.
    user_id : int
        User ID identifying which groups to process.
    visits : pandas.DataFrame
        Visit schedule data from Rubin Schedule Viewer containing ra,
        dec, execution_status, and obs_id columns.
    date : str
        Date string (YYYY-MM-DD) for which to process data.
    shared_state : SharedState
        Thread-safe container for dashboard state. Progress updates are
        written atomically via the write() method.

    Notes
    -----
    - Designed to run in a background thread
    - Updates progress and progress_msg in shared state atomically
    - Processes groups in database order (by group_id)
    - Each group processes its member targets and computes masks
    """

    # Access the groups table, specifying ordering by group_id:
    cur.execute("SELECT group_id, ra_gr, dec_gr FROM groups WHERE user_id = %s ORDER BY group_id",
        (user_id,))
    rows = cur.fetchall()
    n_groups = len(rows)

    # Loop through all groups:
    for i, row in enumerate(rows):

        # Get the Rubin LSST visits for the group pointings:
        visits_use = get_metadata_rsv(visits, row['ra_gr'], row['dec_gr'])

        # Calculate the masks and visits at each target:
        _process_group(row['group_id'], date, visits_use, camera, conn)

        shared_state.write(
            progress=(i + 1) / n_groups,
            progress_msg=f"UPDATING... processing group {i+1}/{n_groups}",
        )

    return