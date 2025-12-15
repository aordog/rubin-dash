#!/usr/bin/env python3
#from utils.util_data import get_camera
#from utils.util_data import get_cursor
import sys
import utils.util_data as util_data
from astropy.time import Time
import numpy as np
import subprocess
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def get_data(RA_t, dec_t, d_t, ra, dec, band, tmjd, camera, cursor):

    # Run the query to get all visits within range of target:
    ra_vals, dec_vals, rot_vals  = util_data.run_query(RA_t, 
                                                       dec_t, 
                                                       d_t, 
                                                       band,
                                                       tmjd,
                                                       cursor)

    # Build the mask from all query visit results:
    mask = util_data.lsstcam_mask(ra, 
                                  dec, 
                                  ra_vals, 
                                  dec_vals, 
                                  rot_vals, 
                                  camera)

    return mask


def write_data_filters(RA_t, dec_t, d_t, ra, dec, date, camera, cursor):

    tmjd = Time(date, format='iso', scale='utc').mjd
    print(tmjd)
    
    filter_names = ['u', 'g', 'r', 'i', 'z', 'y']
    mask_dict = {}
    mask_dict['ra']  = ra
    mask_dict['dec'] = dec

    for band in filter_names:
        mask_dict[band] = get_data(RA_t, 
                                   dec_t, 
                                   d_t,
                                   ra,
                                   dec,
                                   '"'+band+'"',
                                   tmjd,
                                   camera, 
                                   cursor)

    np.save('data/'+date+'.npy', mask_dict)
        
    return 

def check_for_file(RA_t, dec_t, d_t, date):

    ls_data = subprocess.run(["ls","data"],stdout=subprocess.PIPE).stdout.splitlines()
    files = []
    for file in ls_data:
        files.append(file.strip().decode("utf-8").strip('.npy'))

    if date in files:
        print('data exists')
        file_exist = True
    else:
        print('need to get data - NOT LINKED YET')
        file_exist = False

    return file_exist


def generate_dashboard(RA_t, dec_t, d_t, date):

    print('making the dashboard!')

    filter_names = [["'u'", "'g'", "'r'"], ["'i'", "'z'", "'y'"]]

    titles = ['Filter u','Filter g','Filter r','Filter i','Filter z','Filter y',]

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles = titles,
        specs=[[{"type": "image"}, {"type": "image"}, {"type": "image"}],
            [{"type": "image"}, {"type": "image"}, {"type": "image"}]],
        vertical_spacing=0.05
    )

    for row in range(1, 3):  # rows 1 and 2
        for col in range(1, 4):  # cols 1, 2, and 3

            #mask, ra, dec = make_mask_lsstcam(RA_t, dec_t, ra_vals, dec_vals, rot_vals, d_t=d_t)

            #fig.add_trace(go.Heatmap(z=mask, x=ra, y=dec, zmin=0, zmax=20,
            #                            name=filter_names[row-1][col-1],  # Use filter name instead of "trace N"
            #                            hovertemplate='RA: %{x}&deg;<br>Dec: %{y}&deg;<br>visits: %{z}<extra></extra>',
            #                            colorbar=dict(outlinewidth=1, outlinecolor='black')
            #                    ), row=row, col=col)
                
            fig.update_xaxes(range=[RA_t+d_t/2, RA_t-d_t/2], constrain='domain', 
                            row=row, col=col)
            fig.update_yaxes(range=[dec_t-d_t/2, dec_t+d_t/2],  constrain='domain', 
                            scaleanchor=f"x{col + (row-1)*3}", 
                            scaleratio=1, row=row, col=col)
        
            fig.for_each_annotation(lambda a: a.update(font_size=24, y=a.y-0.006))
            #except:
            #    pass

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
    fig.update_layout(height=700, width=900, showlegend=True)
    fig.write_html("all_filters_test_new.html")

    return


def main(only_write_data = False):
    

    if len(sys.argv) < 4:
        print("Must provide: date ('yyyy-mm-dd') RA (deg) dec (deg) width (deg)")
    else:
        print(f"Making plots for {sys.argv[1]}")
        print(f"RA: {sys.argv[2]} degrees")
        print(f"dec: {sys.argv[3]} degrees")
        print(f"Width of patch: {sys.argv[4]} degrees")

        # Make array of RA and dec grid values:
        ra, dec = util_data.ra_dec_flatgrid(float(sys.argv[2]), 
                                            float(sys.argv[3]), 
                                            float(sys.argv[4]))
        
        file_exist = check_for_file(float(sys.argv[2]), 
                                    float(sys.argv[3]), 
                                    float(sys.argv[4]),
                                    sys.argv[1])

        if file_exist == False:

            # Get camera and cursor
            camera = util_data.get_camera()
            cursor = util_data.get_cursor()

            write_data_filters(float(sys.argv[2]), 
                            float(sys.argv[3]), 
                            float(sys.argv[4]),
                            ra,
                            dec,
                            sys.argv[1],
                            camera, 
                            cursor)
            
        generate_dashboard(float(sys.argv[2]), 
                           float(sys.argv[3]), 
                           float(sys.argv[4]),
                           sys.argv[1])

        
        

        

    
    
# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    main()