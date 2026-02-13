"""
utils.py
========

**Author:** Anna Ordog

**Description:**

"""

import numpy as np
import requests
import pandas as pd


def get_metadata_rsv(date: str, 
                     ra_t: float, 
                     dec_t: float, 
                     r_ang: float) -> dict:
    """Read in meta data from the Rubin Schedule Viewer using input parameters.

    See ~tutorial/Commissioning/102_rubin_schedule_viewer.ipynb for how to use
    the Schedule Viewer. The code below is based on that notebook.

    Parameters
    ----------
    date : string
        The date for which to read in the meta data.
    ra_t : float
        The right ascension of the target position (in degrees).
    dec_t : float
        The declination of the target position (in degrees).
    r_ang : float
        The radial distance from the target to search for visits.

    Returns
    -------
    dictionary
        Containing the ra, dec and bands for each visit containing the target.

    """
    
    # Get the data
    visits = rsv_service(date)
    
    ra  = np.array(visits["s_ra"])
    dec = np.array(visits["s_dec"])
    status = np.array(visits["execution_status"])
    obs_id = visits["obs_id"]

    idxs = target_visits_idxs(ra_t, dec_t, r_ang, ra, dec, status)

    metadata = {}
    metadata['ra'] = ra[idxs]
    metadata['dec'] = dec[idxs]
    #metadata['band'] = 
    
    return metadata


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
