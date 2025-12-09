#!/usr/bin/env python3
#from utils.util_data import get_camera
#from utils.util_data import get_cursor
import utils.util_data as util_data

def get_data(RA_t, dec_t, d_t, band):

    camera = util_data.get_camera()
    cursor = util_data.get_cursor()

    ra_vals, dec_vals, rot_vals  = util_data.run_query(RA_t, dec_t, '"'+band+'"', cursor, d_t=d_t)

    mask, ra, dec = util_data.lsstcam_mask(RA_t, dec_t, ra_vals, dec_vals, rot_vals, camera, d_t=d_t)


    return mask, ra, dec


def write_data(RA_t, dec_t, d_t, band, mask, ra, dec):

    mask_dict = {}
    
    for row in range(1, 3):  # rows 1 and 2
        for col in range(1, 4):  # cols 1, 2, and 3

            ra_vals, dec_vals, rot_vals  = run_query(RA_t, dec_t, filter_names[row-1][col-1], 
                                                         cursor, d_t=d_t)
            mask, ra, dec = make_mask_lsstcam(RA_t, dec_t, ra_vals, dec_vals, rot_vals, d_t=d_t)

    
    return



def main(only_write_data = False):
    
    print('running main code')

    filter_names = [["'u'", "'g'", "'r'"], ["'i'", "'z'", "'y'"]]

    if only_write_data:
        print('only writing out data')


        

    
# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    main()