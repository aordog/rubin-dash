#!/usr/bin/env python
import matplotlib.pyplot as plt
import numpy as np
import os
import sqlite3
from rubin_scheduler.utils import LsstCameraFootprint, _angular_separation


def get_camera(os_env = '/rubin/rubin_sim_data'):

    print('Getting camera')
    os.environ['RUBIN_SIM_DATA_DIR'] = os_env
    camera = LsstCameraFootprint(units='degrees')

    return camera


def get_cursor(db_filename = '/rubin/cst_repos/tutorial-notebooks-data/data/lsstcam_20250930.db'):

    print('Getting cursor')
    db_conn = sqlite3.connect(db_filename)
    cursor = db_conn.cursor()

    return cursor
    


def lsstcam_mask(pointing_ra, pointing_dec, ra_vals, dec_vals, rot_vals, camera, d_t=4, samp=0.01):

    radius = d_t/2

    ra = np.arange(pointing_ra - radius*np.cos(np.radians(pointing_dec)), 
                   pointing_ra + radius, 
                   samp * np.cos(np.radians(pointing_dec)))
    
    dec = np.arange(pointing_dec - radius*np.cos(np.radians(pointing_dec)), 
                    pointing_dec + radius, 
                    samp)
    
    ra, dec = np.meshgrid(ra, dec)
    ra  = ra.flatten()
    dec = dec.flatten()

    mask = np.zeros(len(ra))

    for i in range(0,len(ra_vals)):
        idx_visit = camera(ra, dec, ra_vals[i], dec_vals[i], rot_vals[i])
        mask[idx_visit] = mask[idx_visit] + 1

    return mask, ra, dec


def run_query(RA_t, dec_t, band, cursor, d_t=4):

    RA_min = str(RA_t - d_t)
    RA_max = str(RA_t + d_t)
    dec_min = str(dec_t - d_t)
    dec_max = str(dec_t + d_t)
    
    query = """SELECT fieldRA, fieldDec, rotSkyPos, band, observationId, seq_num FROM observations
               WHERE fieldRA < """+RA_max+"""  AND fieldRA > """+RA_min+""" 
                AND fieldDec < """+dec_max+""" AND fieldDec > """+dec_min+""" 
                AND band = """+band+"""; """

    cursor.execute(query)
    results = cursor.fetchall()
    print("Number of observations found for band ",band, ":",  len(results))
    #print(results)

    ra_vals  = np.array(np.array(results)[:,0],dtype=float)
    dec_vals = np.array(np.array(results)[:,1],dtype=float)
    rot_vals = np.array(np.array(results)[:,2],dtype=float)

    return ra_vals, dec_vals, rot_vals