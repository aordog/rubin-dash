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


def get_metadata_rsv(today: str, 
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
    visits = rsv_service(today)
    
    ra  = np.array(visits["s_ra"])
    dec = np.array(visits["s_dec"])
    status = np.array(visits["execution_status"])
    obs_id = visits["obs_id"]

    idxs = target_visits_idxs(ra_t, dec_t, r, ra, dec, status)

    if data is None:
        data = {today:{}}
    else:
        data[today] = {}
    data[today]['ra'] = ra[idxs]
    data[today]['dec'] = dec[idxs]
    data[today]['band'] = ["u"] * len(idxs)

    data = count_visits(today, data)
    
    return data


def count_visits(today: str, data: dict):

    for band in ['u','g','r','i','z','y']:
        idx_band = np.where(np.array(data[today]['band']) == band)
        if idx_band != None:
            data[today][band+'visits'] = len(idx_band[0])
        else:
            data[today][band+'visits'] = 0

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
    visits_dict['RA']  = []
    visits_dict['dec'] = []

    for target in target_set:
        visits_dict['RA'].append(target.ra_t)
        visits_dict['dec'].append(target.dec_t)

    for band in bands:
        visits_dict[band] = total_visits(target_set, band)

    table = pd.DataFrame(visits_dict, index=id)
    table.index.name = "Target ID"
    table = table.reset_index() # moves "Target ID" into a normal column

    return table


def total_visits(target_set, band):

    visits = []
    for target in target_set:
        visits.append(sum(d[band+"visits"] for d in target.data.values()))

    return visits

def time_series(target):

    t = []
    Nvisits = {}

    bands = ['u','g','r','i','z','y']
    for band in bands:
        Nvisits[band] = []

    for date in target.data.keys():
        t.append(date)
        for band in bands:
            Nvisits[band].append(target.data[date][band+'visits'])

    return t, Nvisits


def visits_maps(target, date):

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

    #Nmax = 30
    for row in range(1, 3):  # rows 1 and 2
        for col in range(1, 4):  # cols 1, 2, and 3

            fig.add_trace(
                go.Scatter(
                            x=target.data[date]['ra'],
                            y=target.data[date]['dec'],
                            mode='markers',
                            marker=dict(
                                size=5,
                                color='black',
                                symbol='circle'
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

def visits_plots(target):
 
    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"type": "scatter"}]]
    )

    filter_names = ['u', 'g', 'r', 'i', 'z', 'y']
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    msizes = [18, 16, 14, 12, 10, 8]

    t, Nvisits = time_series(target)

    # Loop through and add traces
    for color, name, s in zip(colors, filter_names, msizes):
        #print(name)
        fig.add_trace(
            go.Scatter(
                x=t,
                y=Nvisits[name],
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