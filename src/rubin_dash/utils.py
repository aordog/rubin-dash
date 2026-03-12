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


def get_metadata_rsv(today: str,
                     visits, 
                     ra_t: float, 
                     dec_t: float, 
                     r: float,
                     data: dict):
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
    
    # Get the data
    #visits = rsv_service(today)
    
    ra  = np.array(visits["s_ra"])
    dec = np.array(visits["s_dec"])
    status = np.array(visits["execution_status"])
    obs_id = visits["obs_id"]

    idxs = target_visits_idxs(ra_t, dec_t, r, ra, dec, status)

    if data is None:
        data = {'daily':{}, 'total':{}}
    data['daily'][today] = {}
    data['daily'][today]['ra'] = ra[idxs]
    data['daily'][today]['dec'] = dec[idxs]
    data['daily'][today]['band'] = make_fake_bands(len(idxs))
    data['daily'][today]['rot'] = make_fake_rot(len(idxs))
    
    return data

def make_fake_bands(nvisits):

    bands = ['u','g','r','i','z','y']

    return random.choices(bands, k=nvisits)

def make_fake_rot(nvisits):

    return [random.uniform(0, 90) for _ in range(nvisits)]


def count_target_visits(today: str,
                        ra_t: float, 
                        dec_t: float,
                        ra_grid: np.ndarray, 
                        dec_grid: np.ndarray,
                        data: dict):

    dist = np.sqrt((ra_t-ra_grid)**2 + ((dec_t-dec_grid)*np.cos(dec_t*np.pi/180.))**2)

    idx = dist.argmin()

    for band in ['u','g','r','i','z','y']:
        data['daily'][today][band+'visits_t'] = data['daily'][today][band+'mask'][idx]
        data['total'][band+'visits_t'] = data['total'][band+'mask'][idx]

    return data


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


def add_mask_grid(pointing_ra, pointing_dec, radius):

    samp=0.01

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

def get_camera(os_env = '/home/aordog/rubin_sim_data'):

    from rubin_scheduler.utils import LsstCameraFootprint, _angular_separation
    print('Getting camera')
    os.environ['RUBIN_SIM_DATA_DIR'] = os_env
    camera = LsstCameraFootprint(units='degrees')

    return camera

def lsstcam_mask(today: str, 
                camera,
                ra_grid: np.ndarray, 
                dec_grid: np.ndarray,
                data: dict):

    #camera = get_camera()

    bands = ['u','g','r','i','z','y']
    for band in bands:

        data['daily'][today][band+'mask'] = np.zeros(len(ra_grid))
        # Check for existing cumulative mask and set up if none yet:
        if data['total'].get(band+'mask') is None:
            #print('no cumulative data yet')
            data['total'][band+'mask'] = np.zeros(len(ra_grid))

        idxs = np.where(np.array(data['daily'][today]['band']) == band)[0]
        for i in idxs:
           idx_visit = camera(ra_grid, dec_grid, 
                              data['daily'][today]['ra'][i], 
                              data['daily'][today]['dec'][i], 
                              data['daily'][today]['rot'][i])
           data['daily'][today][band+'mask'][idx_visit] = data['daily'][today][band+'mask'][idx_visit] + 1
           data['total'][band+'mask'][idx_visit] = data['total'][band+'mask'][idx_visit] + 1

    return data


def target_visits_idxs(ra_t: float, 
                       dec_t: float, 
                       r_ang: float,
                       ra: np.ndarray,
                       dec: np.ndarray,
                       status: np.ndarray) -> np.ndarray:

    dist = np.sqrt((ra_t-ra)**2 + ((dec_t-dec)*np.cos(dec_t*np.pi/180.))**2)

    return np.array(np.where((dist < r_ang) & (status=='Performed'))[0])


def make_table(target_set):

    id = [f"{i:02d}" for i in range(1, len(target_set)+1)]

    bands = ["u", "g", "r", "i", "z", "y"]

    visits_dict = {}
    visits_dict['Name'] = []
    visits_dict['RA']  = []
    visits_dict['dec'] = []
    
    for band in bands:
        visits_dict[band] = []

    for target in target_set:
        visits_dict['Name'].append(target.name)
        visits_dict['RA'].append(target.ra_t)
        visits_dict['dec'].append(target.dec_t)

        for band in bands:
            visits_dict[band].append(int(target.data['total'][band+'visits_t']))

    table = pd.DataFrame(visits_dict, index=id)
    table.index.name = "ID"
    table = table.reset_index() # moves "Target ID" into a normal column

    return table


def time_series(target):

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
            Nvisits_today = target.data['daily'][date][band+'visits_t']
            Nvisits_daily[band].append(Nvisits_today)

            # Total visits:
            Nvisits_tot[band].append(Nvisits_prev_tot[band] + Nvisits_today)
            #print(Nvisits_today, Nvisits_prev_tot[band], Nvisits_tot[band])

            # Update previous total tracker:
            Nvisits_prev_tot[band] = Nvisits_tot[band][-1].copy()
            
            #Nvisits_daily[band].append(target.data[maptype][date][band+'visits_t'])

    return t, Nvisits_daily, Nvisits_tot

def visits_maps(target, date, maptype):

    filter_names = [['u', 'g', 'r'], ['i', 'z', 'y']]
    titles = ['Filter u','Filter g','Filter r','Filter i','Filter z','Filter y',]

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
                z = target.data[maptype][date][filter_names[row-1][col-1]+'mask']
            if maptype == 'total':
                #print('switching to total!')
                z = target.data[maptype][filter_names[row-1][col-1]+'mask']

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
                                                                font=dict(size=14))
                                            )
                            ), 
                            row=row, col=col
            )
                
            fig.update_xaxes(range=[target.ra_t+target.r, target.ra_t-target.r], constrain='domain', 
                            row=row, col=col)
            fig.update_yaxes(range=[target.dec_t-target.r, target.dec_t+target.r], constrain='domain', 
                            scaleanchor=f"x{col + (row-1)*3}", 
                            scaleratio=1, row=row, col=col)
        
            fig.for_each_annotation(lambda a: a.update(font_size=24, y=a.y+0.001))

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
    fig.update_layout(height=700, width=980, showlegend=True)

    fig_html = fig.to_html(include_plotlyjs='cdn', full_html=False, div_id='figure1')
    
    return fig_html

def visits_plots(target, maptype):
 
    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"type": "scatter"}]]
    )

    filter_names = ['u', 'g', 'r', 'i', 'z', 'y']
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    msizes = [18, 16, 14, 12, 10, 8]

    t, Nvisits_daily, Nvisits_tot = time_series(target)

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
    fig.update_layout(height=500, width=980, showlegend=True)

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
    fig.update_layout(height=300, width=980, showlegend=True)
    fig.update_yaxes(range=[-90, 90],row=1, col=1) 
    fig.update_xaxes(range=[t_utc.mjd[0], t_utc.mjd[-1]], row=1, col=1) 

    # For the second figure, we don't need to include plotly.js again
    fig_html = fig.to_html(include_plotlyjs=False, full_html=False, div_id='figure3')

    return fig_html