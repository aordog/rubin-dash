"""
database.py: code for LSST and local databases.

Main functions:

1. set_up_db:
Create the database using the defined schema.

2. initialize_tracking:
Load the requested list of targets into the database and get the LSST camera
information.

3. populate_database:
When querying a new day, populate the database with latest visits information.

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


def read_csv_file(file_in, declim):

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

def group_targets(ra_list, dec_list, nside):

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

def setup_targets(conn, user_id, list_grouped):
    """Populate groups + members. Run once."""

    cur = conn.cursor()

    for group in list_grouped:

        # Make the grids centred on each group for the masks:
        ra_grid, dec_grid = add_mask_grid(group['ra_gr'], group['dec_gr'])

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

def add_mask_grid(pointing_ra, pointing_dec):

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

def compute_daily_masks(visits_use: dict,
                        camera,
                        ra_grid: np.ndarray, 
                        dec_grid: np.ndarray):

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
    cols = ', '.join(VISIT_COLS)
    phs  = ', '.join(['%s'] * len(VISIT_COLS))

    cur.execute(f"""
        INSERT INTO member_daily_visits
               (time, member_id, {cols})
        VALUES (%s, %s, {phs})
    """, (date, member_id, *[v[b] for b in VISIT_COLS]))

def _insert_member_totals(cur, date, member_id, v):
    cols = ', '.join(VISIT_COLS)
    phs  = ', '.join(['%s'] * len(VISIT_COLS))

    cur.execute(f"""
        INSERT INTO member_totals
               (time, member_id, {cols})
        VALUES (%s, %s, {phs})
    """, (date, member_id, *[v[b] for b in VISIT_COLS]))

def _upsert_masks(cur, gid, mask_type, masks):
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

def compute_visits(ra_mem, dec_mem, ra_grid, dec_grid, mask):

    visits_counts = {}

    dist = np.sqrt((ra_mem-ra_grid)**2 + ((dec_mem-dec_grid)*np.cos(dec_mem*np.pi/180.))**2)
    idx = dist.argmin()

    for listname, maskname in zip(VISIT_COLS, MASK_COLS):
        visits_counts[listname] = float(mask[maskname][idx])

    return visits_counts

def process_group(gid, date, visits, camera, conn):

    """Load one group from DB, compute masks, save → return (memory freed)."""

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    ra_grid, dec_grid, mask_row = read_grid_and_mask(gid, cur)

    if mask_row and mask_row[MASK_COLS[0]] is not None:
        totals = {col: np.frombuffer(mask_row[col], dtype=np.int16).copy() for col in MASK_COLS}
    else:
        totals = {col: np.zeros(len(ra_grid), dtype=np.int16) for col in MASK_COLS}

    # Compute today's masks:
    latest = compute_daily_masks(visits, camera, ra_grid, dec_grid)
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
        total_v = compute_visits(mem['ra_mem'], mem['dec_mem'], ra_grid, dec_grid, totals)
        daily_v = compute_visits(mem['ra_mem'], mem['dec_mem'], ra_grid, dec_grid, latest)
        
        # Save daily and total visits
        _insert_member_totals(cur, date, mem['member_id'], total_v)
        _insert_daily_visits(cur, date, mem['member_id'], daily_v)

    conn.commit()
    
    return

def read_grid_and_mask(gid, cur):

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
    subprocess.run(["dropdb", DB_NAME])
    subprocess.run(["createdb", DB_NAME])
    subprocess.run(["psql", "-d", DB_NAME, "-f", "schema.sql"])
    return


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
    ra_t_list, dec_t_list = read_csv_file(file_in, declim)

    print('====================================================')
    print('')
    print(f"Starting code for {len(ra_t_list)} input targets...")
    print('')

    # Group the targets from the list
    list_grouped = group_targets(ra_t_list, dec_t_list, 16)

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
        setup_targets(conn, user_id, list_grouped)

    # Get the camera information
    camera = get_camera()
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
        visits_use = get_metadata_rsv(visits, row['ra_gr'], row['dec_gr'])

        # Calculate the masks and visits at each target:
        process_group(row['group_id'], date, visits_use, camera, conn)

        with state_lock:
            state["progress"] = (i + 1) / n_groups
            state["progress_msg"] = f"UPDATING... processing group {i+1}/{n_groups}"

    return