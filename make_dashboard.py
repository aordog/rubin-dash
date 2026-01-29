#!/usr/bin/env python3
import sys
import utils.util_data as util_data
import utils.util_dashboard as dashboard
from astropy.time import Time
import numpy as np
import subprocess


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
        print('Data file exists')
        file_exist = True
    else:
        print('Need to produce data file...')
        file_exist = False

    return file_exist


def generate_dashboard(RA_t, dec_t, d_t, date, file_out):

    print('Making the dashboard for ',date)

    mask_data = dashboard.read_in_masks('data/'+date+'.npy')

    dashboard.accumulate_target_visits(mask_data, 
                                       RA_t, 
                                       dec_t, 
                                       'data/test_tseries.txt',
                                       date)

    fig1_html = dashboard.make_mask_map(mask_data, 
                                        RA_t, 
                                        dec_t, 
                                        d_t)
    fig2_html = dashboard.make_visits_plot('data/test_tseries.txt')
    fig3_html = dashboard.make_long_forecast_plot(RA_t, dec_t, date)

    dashboard.build_html(date, 
                         RA_t, 
                         dec_t, 
                         fig1_html, 
                         fig2_html,
                         fig3_html, 
                         file_out)

    return


def main(make_dash = True):

    if len(sys.argv) < 5:
        print("Must provide: date ('yyyy-mm-dd') RA (deg) dec (deg) width (deg)")
    else:
        print(f"Date: {sys.argv[1]}")
        print(f"RA: {sys.argv[2]} degrees")
        print(f"dec: {sys.argv[3]} degrees")
        print(f"Width of patch: {sys.argv[4]} degrees")

        if len(sys.argv) > 5:
            if sys.argv[5] == 'False':
                make_dash = False

        # Make array of RA and dec grid values:
        ra, dec = util_data.ra_dec_flatgrid(float(sys.argv[2]), 
                                            float(sys.argv[3]), 
                                            float(sys.argv[4]))
        
        file_exist = check_for_file(float(sys.argv[2]), 
                                    float(sys.argv[3]), 
                                    float(sys.argv[4]),
                                    sys.argv[1])

        if file_exist == False:

            if make_dash == False:
                print('Only writing data file...')

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
            

        if make_dash:
    
            generate_dashboard(float(sys.argv[2]), 
                               float(sys.argv[3]), 
                               float(sys.argv[4]),
                               sys.argv[1],
                               "all_filters_test_new.html")

        else:
            if file_exist:
                print('Dashboard creation is OFF - doing nothing')

        
        

        

    
    
# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    main()