"""
utils.py
========

**Author:** Anna Ordog

**Description:**

"""

import numpy as np
import requests
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import random # only needed for making fake bands and camera angles for now
import os
from astropy.time import Time
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord
from astropy import coordinates as coord
import ephem
import healpy as hp
import psycopg2
import psycopg2.extras
import subprocess
from datetime import datetime
from rubin_dash.config import VERBOSE, DB_NAME

BANDS = ('u', 'g', 'r', 'i', 'z', 'y')
MASK_COLS = [f'{b}mask' for b in BANDS]
VISIT_COLS = [f'{b}visits' for b in BANDS]

#####################
# Data preparation
#####################

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

def make_fake_src_list(nside, declim):

    idx_list = np.arange(0,hp.nside2npix(nside))

    ra, dec = hp.pix2ang(nside, idx_list, lonlat=True)

    return remove_high_dec(ra.astype(float), 
                           dec.astype(float), declim)

def remove_high_dec(ra_in, dec_in, dec_lim):
    return ra_in[dec_in<dec_lim], dec_in[dec_in<dec_lim]

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

#####################
# Data processing 
#####################

def get_metadata_rsv(visits, 
                     ra_t: float, 
                     dec_t: float):
    """Read in meta data from the Rubin Schedule Viewer using input parameters.

    See ~tutorial/Commissioning/102_rubin_schedule_viewer.ipynb for how to use
    the Schedule Viewer. The code below is based on that notebook.

    Parameters
    ----------
    today : string
        The date for which to read in the meta data.
    ra_t : float
        The right ascension of the target position (in degrees).
    dec_t : float
        The declination of the target position (in degrees).
    r     : float
        The radial distance from the target to search for visits.

    Returns
    -------
    dictionary
        Containing the ra, dec and bands for each visit containing the target.

    """

    r = 3.0
    ra  = np.array(visits["s_ra"])
    dec = np.array(visits["s_dec"])
    status = np.array(visits["execution_status"])
    obs_id = visits["obs_id"]

    idxs = target_visits_idxs(ra_t, dec_t, r, ra, dec, status)

    visits_use = {}
    visits_use['ra'] = ra[idxs]
    visits_use['dec'] = dec[idxs]
    visits_use['band'] = make_fake_bands(len(idxs))
    visits_use['rot'] = make_fake_rot(len(idxs))

    return visits_use

def target_visits_idxs(ra_t: float, 
                       dec_t: float, 
                       r_ang: float,
                       ra: np.ndarray,
                       dec: np.ndarray,
                       status: np.ndarray) -> np.ndarray:

    dist = np.sqrt((ra_t-ra)**2 + ((dec_t-dec)*np.cos(dec_t*np.pi/180.))**2)

    return np.array(np.where((dist < r_ang) & (status=='Performed'))[0])

def make_fake_bands(nvisits):

    bands = ['u','g','r','i','z','y']

    return random.choices(bands, k=nvisits)

def make_fake_rot(nvisits):

    return [random.uniform(0, 90) for _ in range(nvisits)]

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

def compute_visits(ra_mem, dec_mem, ra_grid, dec_grid, mask):

    visits_counts = {}

    dist = np.sqrt((ra_mem-ra_grid)**2 + ((dec_mem-dec_grid)*np.cos(dec_mem*np.pi/180.))**2)
    idx = dist.argmin()

    for listname, maskname in zip(VISIT_COLS, MASK_COLS):
        visits_counts[listname] = float(mask[maskname][idx])

    return visits_counts

#####################
# Writing to tables
#####################

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

#####################
# Rubin services
#####################

def rsv_service(date: str) -> pd.DataFrame:

    # Define search parameters from inputs
    params = {"time": "24", "start": date}
    
    # Define the ObsLocTAP URL of the service, which runs at the US Data Facility at SLAC:
    obsloctap_url = "https://usdf-rsp.slac.stanford.edu/obsloctap"

    # Define the schedule URL and connect to it using requests package:
    schedule_url = obsloctap_url + "/schedule"
    response = requests.get(schedule_url, params=params)

    # Assert that the service is alive. - implement as test going forward
    assert response.status_code == 200, f"request failed with status {response.status_code}"
    print(f"Rubin Schedule Forecast  at {response.url} is alive.")
    print(response.url)

    return pd.DataFrame(response.json())

def get_camera(os_env = '/home/aordog/rubin_sim_data'):

    from rubin_scheduler.utils import LsstCameraFootprint, _angular_separation
    print('Getting camera')
    os.environ['RUBIN_SIM_DATA_DIR'] = os_env
    camera = LsstCameraFootprint(units='degrees')

    return camera

#####################
# Table and plots
#####################

def populate_table(cur):

    cur.execute(f"""
        SELECT g.name_gr, g.group_id,
               m.member_id, m.ra_mem, m.dec_mem,
               {', '.join(f't.{c}' for c in VISIT_COLS)}
        FROM members m
        JOIN groups g ON g.group_id = m.group_id
        LEFT JOIN (
            SELECT DISTINCT ON (member_id)
                   member_id, {', '.join(VISIT_COLS)}
            FROM member_totals
            ORDER BY member_id, time DESC
        ) t ON t.member_id = m.member_id
        ORDER BY g.group_id, m.member_id
    """)
    rows = cur.fetchall()
    data = {}

    for col in ['row_id','gr_name','ra','dec','gr_num','mem_num']:
        data[col] = []
    for b in BANDS:
        data[b] = []

    prev_gid, mem_idx = None, 0
    for n, r in enumerate(rows):
        if r['group_id'] != prev_gid:
            prev_gid = r['group_id']
            mem_idx = 0
        else:
            mem_idx += 1

        data['gr_name'].append(r['name_gr'])
        data['ra'].append(r['ra_mem'])
        data['dec'].append(r['dec_mem'])
        data['gr_num'].append(r['group_id'])
        data['mem_num'].append(mem_idx)
        data['row_id'].append(f"{n:02d}")

        for b in BANDS:
            data[b].append(int(r[f'{b}visits'] or 0))

    return data

def make_html_table(data):

    df = pd.DataFrame(data, index=data['row_id'])
    df.index.name = "ID"

    # Define debug columns that should only be shown if VERBOSE is True
    debug_cols = ['row_id', 'gr_name', 'gr_num', 'mem_num']
    if not VERBOSE:
        df = df.drop(columns=debug_cols, errors='ignore')

    html = '<table class="data-table sortable-table">\n<thead>\n<tr>'

    # Index header first, then column headers
    html += f"<th>{df.index.name}</th>"
    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr>\n</thead>\n<tbody>\n"

    # Data rows
    for idx, row in df.iterrows():
        html += (
            f'<tr data-id="{idx}"'
            f' data-gn="{data["gr_num"][list(data["row_id"]).index(idx)]}"'
            f' data-mn="{data["mem_num"][list(data["row_id"]).index(idx)]}">'
        )
        html += f"<td>{idx}</td>"          # ID cell
        for col in df.columns:
            if col in BANDS:
                html += f"<td>{int(row[col])}</td>"
            else:
                html += f"<td>{row[col]}</td>"
        html += "</tr>\n"

    html += "</tbody>\n</table>"
    return html

def populate_2D_map(gid, cur):

    # Group-level data
    cur.execute("""
        SELECT ra_gr, dec_gr, ra_grid, dec_grid
        FROM groups WHERE group_id = %s
    """, (gid,))
    grp = cur.fetchone()

    data = {}

    data['ra_gr']    = grp['ra_gr']
    data['dec_gr']   = grp['dec_gr']
    data['ra_grid']  = np.frombuffer(grp['ra_grid'])
    data['dec_grid'] = np.frombuffer(grp['dec_grid'])

    # Member coordinates
    cur.execute("""
        SELECT ra_mem, dec_mem FROM members
        WHERE group_id = %s ORDER BY member_id
    """, (gid,))
    members = cur.fetchall()
    data['ra_mem']  = np.array([m['ra_mem']  for m in members])
    data['dec_mem'] = np.array([m['dec_mem'] for m in members])

    # Masks
    cols = ', '.join(MASK_COLS)
    cur.execute(f"""
        SELECT mask_type, {cols}
        FROM group_masks
        WHERE group_id = %s AND mask_type IN ('latest', 'total')
    """, (gid,))

    data['masks'] = {}
    for row in cur.fetchall():
        mtype = row['mask_type']
        data['masks'][mtype] = {col: np.frombuffer(row[col], dtype=np.int16) for col in MASK_COLS}

    n = len(data['ra_grid'])
    for mtype in ('latest', 'total'):
        if mtype not in data['masks']:
            data[mtype] = {col: np.zeros(n) for col in MASK_COLS}

    return data

def make_html_visits_map(data, idx_mem, maptype):

    filter_names = [BANDS[0:3], BANDS[3:6]]
    mask_names = [MASK_COLS[0:3],MASK_COLS[3:6]]
    specs = [[{"type": "scatter"}]*3]*2

    fig = make_subplots(rows=2, cols=3,
                        subplot_titles = BANDS,
                        specs = specs,
                        vertical_spacing=0.1,
                        horizontal_spacing=0.01)
    title = f"<b>RA = {data['ra_mem'][0]}&deg;, dec = {data['dec_mem'][0]}&deg;</b>"
    fig.update_layout(title=dict(text=title, x=0.5, xanchor="center"))

    Nmax = 20
    for row in range(1, 3):  # rows 1 and 2
        for col in range(1, 4):  # cols 1, 2, and 3

            if maptype == 'daily':
                z = data['masks']['latest'][mask_names[row-1][col-1]]
            if maptype == 'total':
                z = data['masks']['total'][mask_names[row-1][col-1]]

            fig.add_trace(go.Heatmap(z=z, x=data['ra_grid'], y=data['dec_grid'], 
                                     zmin=0, zmax=Nmax,
                                     name=filter_names[row-1][col-1], 
                                     hovertemplate='RA: %{x}&deg;<br>Dec: %{y}&deg;<br>visits: %{z}<extra></extra>',
                                     colorbar=dict(outlinewidth=1, 
                                                   outlinecolor='black', 
                                                   title=dict(text='Number of visits',
                                                                side='right',
                                                                font=dict(size=12)))
                                    ),row=row, col=col)
            
            fig.add_trace(go.Scatter(x=data['ra_mem'], y=data['dec_mem'],
                                    showlegend=False, mode='markers',
                                    marker=dict(size=3,
                                                color='black',
                                                symbol='circle')
                                    ),row=row, col=col)
            fig.add_trace(go.Scatter(x=[data['ra_mem'][idx_mem]],y=[data['dec_mem'][idx_mem]],
                                    mode='markers',showlegend=False,
                                    marker=dict(size=5,
                                                color='lightgreen',
                                                symbol='circle')
                                    ),row=row, col=col)    
                
            fig.update_xaxes(range=[data['ra_gr']+2.5, data['ra_gr']-2.5], constrain='domain', 
                            row=row, col=col)
            fig.update_yaxes(range=[data['dec_gr']-2.5, data['dec_gr']+2.5], constrain='domain', 
                            scaleanchor=f"x{col + (row-1)*3}", 
                            scaleratio=1, row=row, col=col)
            fig.for_each_annotation(lambda a: a.update(font_size=16, y=a.y+0.001))

    fig.update_xaxes(showline=True, linewidth=1, linecolor='black', mirror=True,
                    showgrid=False, zeroline=False)
    fig.update_yaxes(showline=True, linewidth=1, linecolor='black', mirror=True,
                    showgrid=False, zeroline=False)
    fig.update_xaxes(title_text="RA (deg.)", row=2)
    fig.update_yaxes(title_text="Dec (deg.)", col=1)
    fig.update_layout(showlegend=True, margin=dict(l=60, r=40, t=50, b=50))

    fig.update_layout(autosize=True, width=None, height=None)

    fig_html = fig.to_html(full_html=False, div_id='figure1',
                        config={'responsive': True},
                        include_plotlyjs=False)   # ← rely on the CDN load
    
    return fig_html

def populate_times_series(gid, idx_mem, cur):

    # Daily time series data
    cols = ', '.join([f'v.{c}' for c in VISIT_COLS])
    cur.execute(f"""
        SELECT v.time, {cols}
          FROM member_daily_visits v
          JOIN members m ON v.member_id = m.member_id
         WHERE m.group_id = %s
           AND m.member_idx = %s
         ORDER BY v.time
    """, (gid, idx_mem))

    data = {}

    data['daily'] = pd.DataFrame(cur.fetchall(), columns=['time'] + VISIT_COLS)
    #print(time_df)

    # Cumulative time series data
    cols = ', '.join([f'v.{c}' for c in VISIT_COLS])
    cur.execute(f"""
        SELECT v.time, {cols}
          FROM member_totals v
          JOIN members m ON v.member_id = m.member_id
         WHERE m.group_id = %s
           AND m.member_idx = %s
         ORDER BY v.time
    """, (gid, idx_mem))

    data['total'] = pd.DataFrame(cur.fetchall(), columns=['time'] + VISIT_COLS)

    # Member coordinates
    cur.execute("""
        SELECT ra_mem, dec_mem FROM members
        WHERE group_id = %s ORDER BY member_id
    """, (gid,))
    members = cur.fetchall()
    data['ra_mem']  = np.array([m['ra_mem']  for m in members])
    data['dec_mem'] = np.array([m['dec_mem'] for m in members])
    #data['ra_mem']  = #np.array([m['ra_mem']  for m in members])
    #data['dec_mem'] = #np.array([m['dec_mem'] for m in members])
    #data[] = 
    #data[] = 

    return data

def make_html_visits_plot(data, maptype):

    fig = make_subplots(rows=1, cols=1,specs=[[{"type": "scatter"}]])
    title = f"<b>RA = {data['ra_mem'][0]}&deg;, dec = {data['dec_mem'][0]}&deg;</b>"
    fig.update_layout(title=dict(text=title, x=0.5, xanchor="center"))

    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    msizes = [18, 16, 14, 12, 10, 8]

    # Loop through and add traces
    for color, name, visit, s in zip(colors, BANDS, VISIT_COLS, msizes):

        fig.add_trace(
            go.Scatter(x = pd.to_datetime(data[maptype]['time']),
                       y = data[maptype][visit],
                mode='lines+markers',
                name=name,
                marker=dict(
                    size=s,
                    color=color,
                    symbol='circle'
                )
            ),
            row=1, col=1
        )

    fig.update_xaxes(title_text="Date", row=1)
    fig.update_yaxes(title_text="Number of visits", col=1)
    fig.update_layout(showlegend=True, margin=dict(l=60, r=40, t=50, b=50))

    fig.update_layout(autosize=True, width=None, height=None)

    fig_html = fig.to_html(full_html=False, div_id='figure2',
                        config={'responsive': True},
                        include_plotlyjs=False)   # ← rely on the CDN load

    return fig_html

def populate_observability(gid, idx_mem, cur, date):

    data = {}

    # Extract the RA and dec from group and member indices:
    cur.execute(f"""
        SELECT ra_mem, dec_mem FROM members 
        WHERE group_id = %s AND member_idx =%s
        """, (gid,idx_mem))
    coords = cur.fetchone()
    RA_t  = coords[0]
    dec_t = coords[1]

    ##### Constants - eventually convert to inputs ####
    Ndays  =  30.0 # days
    dt =  5.0/60. # hours

    # Get location of LSST and start date for plot:
    loc = EarthLocation.of_site('LSST')
    start_date = Time(date).iso

    ##### 1) Data for tracking the target #####

    # Set up time array:
    dmjd_arr = np.arange(0, Ndays+1+dt/24., dt/24.)
    t_utc = Time(start_date, format="iso", scale="utc") + dmjd_arr

    # Get alt/az coords of target vs time:
    c = SkyCoord(RA_t, dec_t, frame='icrs', unit='deg')
    aa_frame = coord.AltAz(obstime = t_utc, location = loc)
    c_altaz  = c.transform_to(aa_frame)
    az = c_altaz.az.deg.copy()
    az[az > 180.] = az[az > 180.] - 360.

    data['loc'] = loc
    data['az']  = az
    data['el']  = c_altaz.alt.deg
    data['utc'] = t_utc
    data['ra']  = RA_t
    data['dec'] = dec_t

    ##### 2) Data for tracking sunrise/sunset #####
    
    # Set up array of days (expand 1 day beyond range in both directions):
    days_mjd = np.arange(-1.0, Ndays+1.0, 1.0)
    days_utc = Time(start_date, format="iso", scale="utc") + days_mjd

    # Set up observer object and populate:
    obs = ephem.Observer()
    obs.lon  = str(loc.geodetic.lon.deg) #Note that lon should be string
    obs.lat  = str(loc.geodetic.lat.deg) #Note that lat should be string
    obs.elev = loc.geodetic.height.value

    # Loop through days to get sunrise and sunset times:
    data['sunrise'] = []
    data['sunset']  = []
    data['hours']   = []
    data['days_utc'] = days_utc[1:-1]

    # Loop to record sunrises and sunsets:
    for i in range(0,len(days_utc)):

        obs.date = str(days_utc[i])
        sunrise = obs.next_rising(ephem.Sun()).datetime()
        data['sunrise'].append(sunrise)

        obs.date = str(days_utc[i])
        sunset = obs.next_setting(ephem.Sun()).datetime()
        data['sunset'].append(sunset)

    # Loop to count hours of night-time:
    for i in range(1,len(days_utc)-1):
        idx_count = np.where((Time(t_utc).mjd>Time(data['sunset'][i]).mjd) & 
                             (Time(t_utc).mjd<Time(data['sunrise'][i+1]).mjd) & 
                             (data['el']>15))[0]
        data['hours'].append((Time(t_utc[idx_count[-1]]).mjd - Time(t_utc[idx_count[0]]).mjd)*24.)

    return data

def make_html_obs_plot(data):

    fig = make_subplots(rows=2, cols=1, specs=[[{"type": "scatter"}]]*2)
    title = f"<b>RA = {data['ra']}&deg;, dec = {data['dec']}&deg;</b>"
    fig.update_layout(title=dict(text=title, x=0.5, xanchor="center"))

    fig.add_trace(
        go.Scatter(
            x=data['utc'].iso,
            y=data['el'],
            mode='lines',
            name = 'elevation',
            line=dict(width=1.5, color='yellow')
        ),
        row=2, col=1
    )
    fig.add_hrect(
        y0=-90, y1=0,           # horizontal lines to shade between
        fillcolor="darkolivegreen", 
        opacity=0.7,
        layer="above",
        line_width=0,
        row=2, col=1
    )
    fig.add_hrect(
        y0=0, y1=15,           # horizontal lines to shade between
        fillcolor="gray", 
        opacity=0.7,
        layer="above",
        line_width=0,
        row=2, col=1
    )
    fig.add_hrect(
        y0=86.5, y1=90,           # horizontal lines to shade between
        fillcolor="gray", 
        opacity=0.7,
        layer="above",
        line_width=0,
        row=2, col=1
    )
    for i in range(0,len(data['sunrise'])):
        fig.add_shape(
            type="rect",
            x0=Time(data['sunrise'][i]).iso, 
            x1=Time(data['sunset'][i]).iso,
            y0=15,
            y1=86.5,
            fillcolor="deepskyblue",
            opacity=0.6,
            line_width=0,
            layer="above",
            xref="x2",
            yref="y2"
        )
    for i in range(0,len(data['sunrise'])-1):
        fig.add_shape(
            type="rect",
            x0=Time(data['sunset'][i]).iso, 
            x1=Time(data['sunrise'][i+1]).iso,
            y0=15,
            y1=86.5,
            fillcolor="black",
            line_width=0,
            layer="below",
            xref="x2",
            yref="y2"
        )
    fig.add_trace(
        go.Scatter(
            x=data['days_utc'].iso,
            y=data['hours'],
            mode='lines',
            name = 'elevation',
            line=dict(width=2, color='black')
        ),
        row=1, col=1
    )

    fig.update_xaxes(title_text="Date (UTC)", 
                     range=[data['days_utc'].iso[0], data['days_utc'].iso[-1]], 
                     showgrid=False, tickformat="%d/%m/%y")
    fig.update_yaxes(
        title_text="Hours observable",
        range=[0, 15],
        row=1, col=1,
        showgrid=True,
        tickvals=[0, 3, 6, 9, 12, 15],
        ticktext=['0', '3', '6', '9', '12', '15']
    )
    fig.update_yaxes(
        title_text="Elevation",
        range=[-90, 90],
        showgrid=False,
        zeroline=False,
        tickvals=[-90, -45, 0, 45, 90],
        ticktext=['-90°', '-45°', '0°', '45°', '90°'],
        row=2, col=1
    )
    fig.update_layout(showlegend=False, margin=dict(l=60, r=40, t=50, b=50)) 
    fig.update_layout(autosize=True, width=None, height=None)

    fig_html = fig.to_html(full_html=False, div_id='figure3',
                        config={'responsive': True},
                        include_plotlyjs=False)   # ← rely on the CDN load

    return fig_html

#####################
# Wrapper helper code
#####################


def set_up_db():
    subprocess.run(["dropdb", DB_NAME])
    subprocess.run(["createdb", DB_NAME])
    subprocess.run(["psql", "-d", DB_NAME, "-f", "schema.sql"])
    return

def write(destinations, msg, at_line_start):
    lines = msg.split("\n")

    for i, line in enumerate(lines):
        if i > 0:
            for dest in destinations:
                dest.write("\n")
            at_line_start = True

        if line:
            if at_line_start:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                line = f"[{timestamp}] {line}"
                at_line_start = False
            for dest in destinations:
                dest.write(line)
                dest.flush()

    return at_line_start




