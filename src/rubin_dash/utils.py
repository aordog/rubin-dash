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

    groups = {'name_gr':[],'ra_gr':[],'dec_gr':[],'ra_mem':[],'dec_mem':[]}

    for idx in idx_filled:
        groups['name_gr'].append('nside'+str(nside)+'_'+str(idx))
        coords_group = hp.pix2ang(nside, idx, lonlat=True)
        groups['ra_gr'].append(coords_group[0])
        groups['dec_gr'].append(coords_group[1])
        groups['ra_mem'].append(ra_list[pixel_ids == idx])
        groups['dec_mem'].append(dec_list[pixel_ids == idx])

    return groups

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
# Setting up Target objects
#####################

def initialize_data_dict(data):

    if data is None:
        return {'daily':{}, 'latest':{}, 'total':{}}

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

def make_fake_bands(nvisits):

    bands = ['u','g','r','i','z','y']

    return random.choices(bands, k=nvisits)

def make_fake_rot(nvisits):

    return [random.uniform(0, 90) for _ in range(nvisits)]

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

def count_target_visits(today: str,
                        ra_mem: float, 
                        dec_mem: float,
                        ra_grid: np.ndarray, 
                        dec_grid: np.ndarray,
                        data: dict):

    data['daily'][today] = {}

    for band in ['u','g','r','i','z','y']:

        listname = band+'visits'
        maskname = band+'mask'

        data['daily'][today][listname] = []
        data['total'][listname] = []

        for i in range(0,len(ra_mem)):
            dist = np.sqrt((ra_mem[i]-ra_grid)**2 + ((dec_mem[i]-dec_grid)*np.cos(dec_mem[i]*np.pi/180.))**2)
            idx = dist.argmin()

            data['daily'][today][listname].append(data['latest'][maskname][idx])
            data['total'][listname].append(data['total'][maskname][idx])

    return data

def lsstcam_mask(visits_use: dict,
                camera,
                ra_grid: np.ndarray, 
                dec_grid: np.ndarray,
                data: dict):

    bands = ['u','g','r','i','z','y']
    for band in bands:

        mask_name = band+'mask'

        data['latest'][mask_name] = np.zeros(len(ra_grid))

        # Check for existing cumulative mask and set up if none yet:
        if data['total'].get(mask_name) is None:
            data['total'][mask_name] = np.zeros(len(ra_grid))

        idxs = np.where(np.array(visits_use['band']) == band)[0]
        for i in idxs:
           idx_visit = camera(ra_grid, dec_grid, 
                              visits_use['ra'][i], 
                              visits_use['dec'][i], 
                              visits_use['rot'][i])
           data['latest'][mask_name][idx_visit] = data['latest'][mask_name][idx_visit] + 1
           data['total'][mask_name][idx_visit]  = data['total'][mask_name][idx_visit]  + 1

    return data

def target_visits_idxs(ra_t: float, 
                       dec_t: float, 
                       r_ang: float,
                       ra: np.ndarray,
                       dec: np.ndarray,
                       status: np.ndarray) -> np.ndarray:

    dist = np.sqrt((ra_t-ra)**2 + ((dec_t-dec)*np.cos(dec_t*np.pi/180.))**2)

    return np.array(np.where((dist < r_ang) & (status=='Performed'))[0])

#####################
# Table and plots
#####################

def make_table(target_set):

    bands = ["u", "g", "r", "i", "z", "y"]

    visits_dict = {}
    visits_dict['Name'] = []
    visits_dict['RA']  = []
    visits_dict['dec'] = []
    visits_dict['gr_num']  = []
    visits_dict['mem_num'] = []
    row_ids = []
    
    for band in bands:
        visits_dict[band] = []

    row=0
    #for target in target_set:
    for j in range(0,len(target_set)):
        #visits_dict['Name'].append(target.name)
        #visits_dict['RA'].append(target.ra_t)
        #visits_dict['dec'].append(target.dec_t)
        for i in range(0,len(target_set[j].ra_mem)):
            visits_dict['Name'].append(target_set[j].name_gr)
            visits_dict['RA'].append(target_set[j].ra_mem[i])
            visits_dict['dec'].append(target_set[j].dec_mem[i])
            visits_dict['gr_num'].append(j)
            visits_dict['mem_num'].append(i)
            row_ids.append(f"{row:02d}")
            row=row+1

            for band in bands:
                visits_dict[band].append(int(target_set[j].data['total'][band+'visits'][i]))

    table = pd.DataFrame(visits_dict, index=row_ids)
    table.index.name = "ID"

    return table

def table_to_html(df):
    html = '<table class="data-table">\n<thead>\n<tr>'

    # Index header first, then column headers
    html += f"<th>{df.index.name}</th>"
    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr>\n</thead>\n<tbody>\n"

    # Data rows
    for idx, row in df.iterrows():
        html += (
            f'<tr data-id="{idx}"'
            f' data-gn="{row["gr_num"]}"'
            f' data-mn="{row["mem_num"]}">'
        )
        html += f"<td>{idx}</td>"          # ID cell
        for col in df.columns:
            html += f"<td>{row[col]}</td>"
        html += "</tr>\n"

    html += "</tbody>\n</table>"
    return html

def time_series(target, member):

    t = []
    Nvisits_daily = {}
    Nvisits_tot   = {}
    Nvisits_prev_tot = {}

    bands = ['u','g','r','i','z','y']
    for band in bands:
        Nvisits_prev_tot[band] = 0
        Nvisits_daily[band] = []
        Nvisits_tot[band] = []

    for date in target.data['daily'].keys():
        t.append(date)

        for band in bands:

            # Today's visits:
            Nvisits_today = target.data['daily'][date][band+'visits'][member]
            Nvisits_daily[band].append(Nvisits_today)

            # Total visits:
            Nvisits_tot[band].append(Nvisits_prev_tot[band] + Nvisits_today)

            # Update previous total tracker:
            Nvisits_prev_tot[band] = Nvisits_tot[band][-1].copy()
            
    return t, Nvisits_daily, Nvisits_tot

def visits_maps(target, idx_mem, date, maptype):

    filter_names = [['u', 'g', 'r'], ['i', 'z', 'y']]
    titles = ['u','g','r','i','z','y',]

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles = titles,
        specs=[[{"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}, {"type": "scatter"}]],
        vertical_spacing=0.1,
        horizontal_spacing=0.01
    )

    Nmax = 20
    for row in range(1, 3):  # rows 1 and 2
        for col in range(1, 4):  # cols 1, 2, and 3

            if maptype == 'daily':
                z = target.data['latest'][filter_names[row-1][col-1]+'mask']
            if maptype == 'total':
                #print('switching to total!')
                z = target.data['total'][filter_names[row-1][col-1]+'mask']

            fig.add_trace(go.Heatmap(z=z,
                                     x=target.ra_grid, 
                                     y=target.dec_grid, 
                                     zmin=0, zmax=Nmax,
                                     name=filter_names[row-1][col-1], 
                                     hovertemplate='RA: %{x}&deg;<br>Dec: %{y}&deg;<br>visits: %{z}<extra></extra>',
                                     colorbar=dict(outlinewidth=1, 
                                                   outlinecolor='black', 
                                                   title=dict(text='Number of visits',
                                                                side='right',
                                                                font=dict(size=12))
                                            )
                            ), 
                            row=row, col=col
            )
            fig.add_trace(
            go.Scatter(
                x=target.ra_mem,
                y=target.dec_mem,
                showlegend=False,
                mode='markers',
                marker=dict(
                    size=3,
                    color='black',
                    symbol='circle'
                    )
                ),
                row=row, col=col
            )
            fig.add_trace(
            go.Scatter(
                x=[target.ra_mem[idx_mem]],
                y=[target.dec_mem[idx_mem]],
                mode='markers',
                showlegend=False,
                marker=dict(
                    size=5,
                    color='lightgreen',
                    symbol='circle'
                    )
                ),
                row=row, col=col
            )    
                
            fig.update_xaxes(range=[target.ra_gr+2.5, target.ra_gr-2.5], constrain='domain', 
                            row=row, col=col)
            fig.update_yaxes(range=[target.dec_gr-2.5, target.dec_gr+2.5], constrain='domain', 
                            scaleanchor=f"x{col + (row-1)*3}", 
                            scaleratio=1, row=row, col=col)
        
            fig.for_each_annotation(lambda a: a.update(font_size=16, y=a.y+0.001))

    fig.update_xaxes(
        showline=True, linewidth=1, linecolor='black', mirror=True,
        showgrid=False, zeroline=False
    )
    fig.update_yaxes(
        showline=True, linewidth=1, linecolor='black', mirror=True,
        showgrid=False, zeroline=False
    )

    fig.update_xaxes(title_text="RA (deg.)", row=2)
    fig.update_yaxes(title_text="Dec (deg.)", col=1)
    fig.update_layout(height=500, width=700, showlegend=True)

    fig_html = fig.to_html(include_plotlyjs='cdn', full_html=False, div_id='figure1')
    
    return fig_html

def visits_plots(target, member, maptype):
 
    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"type": "scatter"}]]
    )

    filter_names = ['u', 'g', 'r', 'i', 'z', 'y']
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    msizes = [18, 16, 14, 12, 10, 8]

    t, Nvisits_daily, Nvisits_tot = time_series(target, member)

    # Loop through and add traces
    for color, name, s in zip(colors, filter_names, msizes):

        if maptype == 'daily':
            y = Nvisits_daily[name]
        if maptype == 'total':
            y = Nvisits_tot[name]

        #print(name)
        fig.add_trace(
            go.Scatter(
                x=t,
                y=y,
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
    fig.update_layout(height=400, width=700, showlegend=True)

    # For the second figure, we don't need to include plotly.js again
    fig_html = fig.to_html(include_plotlyjs=False, full_html=False, div_id='figure2')

    return fig_html

def make_long_forecast_plot(date, RA_t, dec_t):

    loc = EarthLocation.of_site('LSST')
    start_date = Time(date).iso
    t  =  30.0 # days
    dt =  1.0 # hours
    dmjd_arr = np.arange(0, t+dt/24., dt/24.)
    t_utc = Time(start_date, format="iso", scale="utc") + dmjd_arr

    c = SkyCoord(RA_t, dec_t, frame='icrs', unit='deg')
    aa_frame = coord.AltAz(obstime = t_utc, location = loc)
    c_altaz  = c.transform_to(aa_frame)

    az = c_altaz.az.deg.copy()
    az[az > 180.] = az[az > 180.] - 360.

    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"type": "scatter"}]]
    )


    fig.add_trace(
        go.Scatter(
            x=t_utc.mjd,
            y=c_altaz.alt.deg,
            mode='lines+markers',
            name = 'elevation',
            marker=dict(
                size=2,
                color='red',
                symbol='circle'
            )
        ),
        row=1, col=1
    )

    fig.add_hrect(
        y0=-90, y1=15,           # horizontal lines to shade between
        fillcolor="gray", 
        opacity=0.8,
        layer="above",
        line_width=0,
        row=1, col=1
    )

    fig.add_hrect(
        y0=86.5, y1=90,           # horizontal lines to shade between
        fillcolor="gray", 
        opacity=0.8,
        layer="above",
        line_width=0,
        row=1, col=1
    )


    #t  =  5.0 # days
    dt =  1.0 # hours
    days_mjd = np.arange(0, t+1.0, 1.0)
    days_utc = Time(start_date, format="iso", scale="utc") + days_mjd
    obs = ephem.Observer()
    obs.lon  = str(loc.geodetic.lon.deg) #Note that lon should be in string format
    obs.lat  = str(loc.geodetic.lat.deg)      #Note that lat should be in string format
    obs.elev = loc.geodetic.height.value

    for day in days_utc:
 
        obs.date = str(day)
        sunrise = obs.next_rising(ephem.Sun()).datetime()
        sunset  = obs.next_setting(ephem.Sun()).datetime()
        #print(sunrise, sunset)

        fig.add_vrect(
            x0=Time(sunrise).mjd, x1=Time(sunset).mjd,          
            fillcolor="gray", 
            opacity=0.8,
            layer="above",
            line_width=0,
            row=1, col=1
        )

    fig.update_xaxes(title_text="MJD", row=1)
    fig.update_yaxes(title_text="Elevation (deg.)", row=1)
    fig.update_layout(height=300, width=700, showlegend=True)
    fig.update_yaxes(range=[-90, 90],row=1, col=1) 
    fig.update_xaxes(range=[t_utc.mjd[0], t_utc.mjd[-1]], row=1, col=1) 

    # For the second figure, we don't need to include plotly.js again
    fig_html = fig.to_html(include_plotlyjs=False, full_html=False, div_id='figure3')

    return fig_html