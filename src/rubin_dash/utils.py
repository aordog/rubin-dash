"""
Utility functions for prototyping and development.

Provides helper functions for the prototyping phase of the dashboard,
including fake data generation (camera angles, filter bands, date ranges)
and coordinate transformations. These are temporary utilities that will be
replaced by real data from the Rubin scheduler as the system matures.

**Author:** Anna Ordog
"""

import numpy as np
import random  # only needed for making fake bands and camera angles
import healpy as hp
from datetime import datetime, timedelta

BANDS = ('u', 'g', 'r', 'i', 'z', 'y')
MASK_COLS = [f'{b}mask' for b in BANDS]
VISIT_COLS = [f'{b}visits' for b in BANDS]


def remove_high_dec(ra_in, dec_in, dec_lim):
    return ra_in[dec_in<dec_lim], dec_in[dec_in<dec_lim]

def make_fake_src_list(nside, declim):

    idx_list = np.arange(0,hp.nside2npix(nside))

    ra, dec = hp.pix2ang(nside, idx_list, lonlat=True)

    return remove_high_dec(ra.astype(float), 
                           dec.astype(float), declim)

def make_fake_bands(nvisits):

    bands = ['u','g','r','i','z','y']

    return random.choices(bands, k=nvisits)

def make_fake_rot(nvisits):
    """Generate fake camera rotation angles for simulated visits.

    Returns random rotation angles in the range [0, 90) degrees for each
    simulated visit. Used in the prototyping phase to simulate realistic
    visit metadata.

    Parameters
    ----------
    nvisits : int
        Number of simulated visits to generate rotation angles for.

    Returns
    -------
    list[float]
        List of rotation angles in degrees, one per visit.
    """
    return [random.uniform(0, 90) for _ in range(nvisits)]


def simulation_dates(sim_start: datetime, sim_end: datetime) -> list[str]:
    """Generate list of simulated survey dates.

    Creates a complete date range from start to end (inclusive) as
    ISO formatted strings. Used for iterating through simulated
    observing nights during the prototyping phase.

    Parameters
    ----------
    sim_start : datetime
        Start date of simulation window.
    sim_end : datetime
        End date of simulation window (inclusive).

    Returns
    -------
    list[str]
        List of YYYY-MM-DD date strings from sim_start to sim_end.
    """
    n_days = (sim_end - sim_start).days + 1
    return [
        (sim_start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(n_days)
    ]




