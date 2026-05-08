"""
observability.py: Functions for calculating observability of targets

Public API
----------
- ``daily_observability`` - Calculate hours source is observable.
- ``elevation_series``    - Calculate elevation versus time.

**Author:** Anna Ordog, for CanDIAPL
"""
from astroplan import FixedTarget, observability_table
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.time import Time
from datetime import timedelta

from rubin_dash.config import OBSERVER, CONSTRAINTS

def daily_observability(ra_t, dec_t, day):

    target = [FixedTarget(coord=SkyCoord(ra=ra_t*u.deg, dec=dec_t*u.deg))]

    time_range = Time([Time(day)-timedelta(days=0.5), Time(day)+timedelta(days=0.5)])
    table = observability_table(CONSTRAINTS, OBSERVER, target, 
                                time_range=time_range, 
                                time_grid_resolution=0.083333*u.hr)
    hrs = table['fraction of time observable'].value[0]*24

    return hrs