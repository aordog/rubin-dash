#!/usr/bin/env python3
#from utils.util_data import get_camera
#from utils.util_data import get_cursor
import sys
import utils.util_data as util_data
from astropy.time import Time
import numpy as np

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


def main(only_write_data = False):
    

    if len(sys.argv) < 4:
        print("Must provide: date ('yyyy-mm-dd') RA (deg) dec (deg) width (deg)")
    else:
        print(f"Accessing data for {sys.argv[1]}")
        print(f"RA: {sys.argv[2]} degrees")
        print(f"dec: {sys.argv[3]} degrees")
        print(f"Width of patch: {sys.argv[4]} degrees")

        # Get camera and cursor
        camera = util_data.get_camera()
        cursor = util_data.get_cursor()

        # Make array of RA and dec grid values:
        ra, dec = util_data.ra_dec_flatgrid(float(sys.argv[2]), 
                                            float(sys.argv[3]), 
                                            float(sys.argv[4]))
        
        write_data_filters(float(sys.argv[2]), 
                           float(sys.argv[3]), 
                           float(sys.argv[4]),
                           ra,
                           dec,
                           sys.argv[1],
                           camera, 
                           cursor)

        

    
    
# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    main()