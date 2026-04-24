"""
lsst.py: Access LSST Schedule Viewer and camera footprint data.

This module provides an interface to the Rubin Schedule Viewer (RSV) service 
and LSST camera geometry data. It enables queries for completed visits at 
specific sky coordinates and provides camera footprint for 2D visits maps.

Public API
----------
- ``rsv_service`` - Query Rubin Schedule Viewer for observations.
- ``get_metadata_rsv`` - Extract visit metadata for a target position.
- ``get_camera`` - Load LSST camera footprint geometry.

**Author:** Anna Ordog, for CanDIAPL
"""

import numpy as np
import pandas as pd
import os
import requests
from rubin_dash.utils import make_fake_bands, make_fake_rot


def _target_visits_idxs(ra_t: float,
                        dec_t: float,
                        r_ang: float,
                        ra: np.ndarray,
                        dec: np.ndarray,
                        status: np.ndarray) -> np.ndarray:
    """Find visit indices within angular distance of target.

    Computes angular distance from a target position to all visits,
    accounting for declination effects on RA distance. Returns indices
    of visits that are within the search radius and have been performed.

    Parameters
    ----------
    ra_t : float
        Target right ascension in degrees.
    dec_t : float
        Target declination in degrees.
    r_ang : float
        Search radius in degrees.
    ra : np.ndarray
        Array of visit right ascensions in degrees.
    dec : np.ndarray
        Array of visit declinations in degrees.
    status : np.ndarray
        Array of visit execution status strings.

    Returns
    -------
    np.ndarray
        Indices of visits within r_ang of target with status=='Performed'.

    """
    dist = np.sqrt(
        (ra_t - ra) ** 2 +
        ((dec_t - dec) * np.cos(dec_t * np.pi / 180.)) ** 2
    )
    return np.array(
        np.where((dist < r_ang) & (status == 'Performed'))[0]
    )


def rsv_service(date: str) -> pd.DataFrame:
    """Query Rubin Schedule Viewer for observation visits.

    Retrieves scheduled observation data from the Rubin Schedule Viewer (RSV) 
    service for a specified date. The service returns visit information 
    including sky coordinates and execution status.

    Parameters
    ----------
    date : str
        Query date in ISO format expected by RSV service.

    Returns
    -------
    pd.DataFrame
        Observation visit data with columns: s_ra, s_dec, execution_status, 
        obs_id, and others from RSV.

    Raises
    ------
    AssertionError
        If the HTTP request to RSV service fails (status != 200).

    Notes
    -----
    The RSV service is hosted at SLAC's Data Facility. Requires internet 
    connectivity to the USDF service endpoint.

    """
    # Define search parameters from inputs
    params = {"time": "24", "start": date}

    # Define the ObsLocTAP URL of the service:
    obsloctap_url = "https://usdf-rsp.slac.stanford.edu/obsloctap"

    # Define the schedule URL and connect to it using requests package:
    schedule_url = obsloctap_url + "/schedule"
    response = requests.get(schedule_url, params=params)

    # Assert that the service is alive:
    assert response.status_code == 200, (
        f"request failed with status {response.status_code}"
    )
    print(f"Rubin Schedule Forecast at {response.url} is alive.")
    print(response.url)

    return pd.DataFrame(response.json())

def get_metadata_rsv(visits,
                     ra_t: float,
                     dec_t: float):
    """Extract visit metadata for a target position from RSV data.

    Filters observation visits from RSV data to find those within a 3-degree 
    search radius of the target coordinates. 

    Parameters
    ----------
    visits : dict or pd.DataFrame
        Visit data from rsv_service().
    ra_t : float
        Target right ascension in degrees.
    dec_t : float
        Target declination in degrees.

    Returns
    -------
    dict
        Dictionary with keys:
        - 'ra': float array of visit RA values for target
        - 'dec': float array of visit Dec values for target
        - 'band': array of bandpass assignments (simulated for now)
        - 'rot': array of rotation angles (simulated for now)

    Notes
    -----
    Search radius is fixed at 3.0 degrees. Only visits with 
    execution_status == 'Performed' are included. Uses helper
    _target_visits_idxs to identify matching visits. Band and rotation 
    data are simulated via make_fake_bands() and make_fake_rot() from utils.py 
    module for now.
    TO DO: when newer LSST databases become available, read in actual values.

    """
    r = 3.0
    ra = np.array(visits["s_ra"])
    dec = np.array(visits["s_dec"])
    status = np.array(visits["execution_status"])
    obs_id = visits["obs_id"]

    idxs = _target_visits_idxs(ra_t, dec_t, r, ra, dec, status)

    visits_use = {}
    visits_use['ra'] = ra[idxs]
    visits_use['dec'] = dec[idxs]
    visits_use['band'] = make_fake_bands(len(idxs))
    visits_use['rot'] = make_fake_rot(len(idxs))

    return visits_use

def get_camera(os_env='/home/aordog/rubin_sim_data'):
    """Load LSST camera footprint geometry.

    Initializes and returns the LSST camera footprint object from
    rubin_scheduler. The footprint defines the instrument's field of
    view and detector geometry.

    Parameters
    ----------
    os_env : str, optional
        Path to rubin_sim data directory. Defaults to
        '/home/aordog/rubin_sim_data'. Set via RUBIN_SIM_DATA_DIR
        environment variable internally.

    Returns
    -------
    rubin_scheduler.utils.LsstCameraFootprint
        Camera footprint object with units='degrees'.

    Notes
    -----
    Requires rubin_scheduler package and its data files to be downloaded
    server-side. Sets the RUBIN_SIM_DATA_DIR environment variable to os_env 
    for the rubin_scheduler package to find required files.

    """
    from rubin_scheduler.utils import (LsstCameraFootprint,
                                       _angular_separation)
    print('Getting camera')
    os.environ['RUBIN_SIM_DATA_DIR'] = os_env
    camera = LsstCameraFootprint(units='degrees')

    return camera