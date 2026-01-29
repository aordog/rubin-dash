#!/usr/bin/env python
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from astropy.time import Time
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord
from astropy import coordinates as coord
import ephem

def read_in_masks(file_in):

    mask_file = np.load(file_in, allow_pickle=True)
    mask_data = mask_file.item()
    #print(mask_data)

    return mask_data

def accumulate_target_visits(mask_data, RA_t, dec_t, time_series, date):

    idx = np.argmin(np.sqrt( (RA_t-mask_data['ra'])**2 + (dec_t-mask_data['dec'])**2 ))

    tmjd = Time(date, format='isot', scale='utc').mjd

    outfile = open(time_series,"a")
    outfile.write(str(tmjd)+" "+
                  str(mask_data['u'][idx])+" "+
                  str(mask_data['g'][idx])+" "+
                  str(mask_data['r'][idx])+" "+
                  str(mask_data['i'][idx])+" "+
                  str(mask_data['z'][idx])+" "+
                  str(mask_data['y'][idx]))
    outfile.write("\n")

    return

def read_target_visits(time_series):

    target_visits = {}

    target_visits['mjd'] = np.genfromtxt(time_series, usecols=0)
    target_visits['u'] = np.genfromtxt(time_series, usecols=1)
    target_visits['g'] = np.genfromtxt(time_series, usecols=2)
    target_visits['r'] = np.genfromtxt(time_series, usecols=3)
    target_visits['i'] = np.genfromtxt(time_series, usecols=4)
    target_visits['z'] = np.genfromtxt(time_series, usecols=5)
    target_visits['y'] = np.genfromtxt(time_series, usecols=6)
 
    return target_visits


def make_mask_map(mask_data, RA_t, dec_t, d_t):

    filter_names = [['u', 'g', 'r'], ['i', 'z', 'y']]
    titles = ['Filter u','Filter g','Filter r','Filter i','Filter z','Filter y',]

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles = titles,
        specs=[[{"type": "image"}, {"type": "image"}, {"type": "image"}],
               [{"type": "image"}, {"type": "image"}, {"type": "image"}]],
        vertical_spacing=0.1,
        horizontal_spacing=0.01
    )

    Nmax = int(np.nanmax([mask_data['u'],mask_data['g'],mask_data['r'],
                      mask_data['i'],mask_data['z'],mask_data['y']]))
    print(Nmax)
    for row in range(1, 3):  # rows 1 and 2
        for col in range(1, 4):  # cols 1, 2, and 3

            fig.add_trace(go.Heatmap(z=mask_data[filter_names[row-1][col-1]], 
                                     x=mask_data['ra'], 
                                     y=mask_data['dec'], 
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
                                    row=row, col=col)
                
            fig.update_xaxes(range=[RA_t+d_t/2, RA_t-d_t/2], constrain='domain', 
                            row=row, col=col)
            fig.update_yaxes(range=[dec_t-d_t/2, dec_t+d_t/2], constrain='domain', 
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


def make_visits_plot(time_series):
 
    target_visits = read_target_visits(time_series)

    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"type": "scatter"}]]
    )

    filter_names = ['u', 'g', 'r', 'i', 'z', 'y']
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    msizes = [18, 16, 14, 12, 10, 8]

    # Loop through and add traces
    for color, name, s in zip(colors, filter_names, msizes):
        #print(name)
        fig.add_trace(
            go.Scatter(
                x=target_visits['mjd'],
                y=target_visits[name],
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

    fig.update_xaxes(title_text="MJD", row=1)
    fig.update_yaxes(title_text="Number of visits", col=1)
    fig.update_layout(height=500, width=980, showlegend=True)

    # For the second figure, we don't need to include plotly.js again
    fig_html = fig.to_html(include_plotlyjs=False, full_html=False, div_id='figure2')

    return fig_html


def make_long_forecast_plot(RA_t, dec_t, date):

    loc = EarthLocation.of_site('LSST')
    start_date = Time(date).iso
    t  =  10.0 # days
    dt =  1.0 # hours
    dmjd_arr = np.arange(0, t+dt/24., dt/24.)
    t_utc = Time(start_date, format="iso", scale="utc") + dmjd_arr

    c = SkyCoord(RA_t, dec_t, frame='icrs', unit='deg')
    aa_frame = coord.AltAz(obstime = t_utc, location = loc)
    c_altaz  = c.transform_to(aa_frame)

    az = c_altaz.az.deg.copy()
    az[az > 180.] = az[az > 180.] - 360.

    fig = make_subplots(
        rows=2, cols=1,
        specs=[[{"type": "scatter"}],[{"type": "scatter"}]]
    )

    fig.add_trace(
        go.Scatter(
            x=t_utc.mjd,
            y=az,
            mode='lines+markers',
            name = 'azimuth',
            marker=dict(
                size=2,
                color='blue',
                symbol='circle'
            )
        ),
        row=1, col=1
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
        row=2, col=1
    )

    fig.add_hrect(
        y0=-90, y1=15,           # horizontal lines to shade between
        fillcolor="gray", 
        opacity=0.8,
        layer="above",
        line_width=0,
        row=2, col=1
    )

    fig.add_hrect(
        y0=86.5, y1=90,           # horizontal lines to shade between
        fillcolor="gray", 
        opacity=0.8,
        layer="above",
        line_width=0,
        row=2, col=1
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
        fig.add_vrect(
            x0=Time(sunrise).mjd, x1=Time(sunset).mjd,          
            fillcolor="gray", 
            opacity=0.8,
            layer="above",
            line_width=0,
            row=2, col=1
        )


    fig.update_xaxes(title_text="MJD", row=1)
    fig.update_xaxes(title_text="MJD", row=2)
    fig.update_yaxes(title_text="Azimuth (deg.)", row=1)
    fig.update_yaxes(title_text="Elevation (deg.)", row=2)
    fig.update_layout(height=700, width=980, showlegend=True)

    fig.update_yaxes(range=[-180, 180], row=1, col=1) 
    fig.update_yaxes(range=[-90, 90],row=2, col=1) 

    fig.update_xaxes(range=[t_utc.mjd[0], t_utc.mjd[-1]], row=1, col=1) 
    fig.update_xaxes(range=[t_utc.mjd[0], t_utc.mjd[-1]],row=2, col=1) 

    # For the second figure, we don't need to include plotly.js again
    fig_html = fig.to_html(include_plotlyjs=False, full_html=False, div_id='figure3')

    return fig_html


def build_html(date, RA_t, dec_t, fig1_html, fig2_html, fig3_html, file_out):

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
            <h1>Target: RA=\\({RA_t}^{{\circ}}\\), dec=\\({dec_t}^{{\circ}}\\)</h1>
            
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


def add_html_refresh(file_in):

    with open(file_in, 'r') as file:
        lines = file.readlines()

    with open(file_in, 'w') as file:
        for line in lines:
            if line.startswith('<head>'):
                print('adding refresh to html')
                file.write(line.strip()+'\n'+'<head><meta http-equiv="refresh" content="5" /></head>'+'\n')
            else:
                file.write(line)

    return
