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

    # Convert figure to HTML div (not a full HTML document)
    # include_plotlyjs='cdn' loads Plotly from the web
    # full_html=False means we only get the <div>, not a complete HTML page
    fig_html = fig.to_html(include_plotlyjs='cdn', full_html=False, div_id='figure1')
    
    return fig_html


def build_html(date, ra_t, dec_t, fig1_html, fig2_html, fig3_html, file_out):

    # Build the complete HTML document
    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <title>Mask Maps - {date}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 10px;
                background-color: white;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
            }}
            h1 {{
                text-align: center;
                color: #333;
                font-size: 36px;
            }}
            h2 {{
                color: #333;
                font-size: 30px;
            }}
            .figure-container {{
                margin: 30px 0;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: white;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Target: RA=\\({ra_t}^{{\circ}}\\), dec=\\({dec_t}^{{\circ}}\\)</h1>
            
            <div class="figure-container">
                <h2>Visits up to {date}</h2>
                {fig1_html}
            </div>
            
            <div class="figure-container">
                <h2>Progress at target</h2>
                {fig2_html}
            </div>

            <div class="figure-container">
                <h2>Future observability of target</h2>
                {fig3_html}
            </div>

        </div>
    </body>
    </html>
    """
    
    # Write the complete HTML to file
    with open(file_out, 'w', encoding='utf-8') as f:
        f.write(html_string)

    #    add_html_refresh(file_out)

    return
