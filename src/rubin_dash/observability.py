"""
observability.py: Functions for calculating observability of targets

Public API
----------
- ``daily_observability`` - Calculate hours source is observable.
- ``elevation_series``    - Calculate elevation versus time.

**Author:** Anna Ordog, for CanDIAPL
"""
from astropy.time import Time
from astropy import coordinates as coord
import numpy as np
import ephem

from rubin_dash.config import LOC

def daily_observability(ra_t, dec_t, day):

    dt =  5.0/60. # hours

    start_date = Time(day).iso

    # Set up time array:
    dmjd_arr = np.arange(0, 2+dt/24., dt/24.)
    t_utc = Time(start_date, format="iso", scale="utc") + dmjd_arr

    # Get alt/az coords of target vs time:
    c = coord.SkyCoord(ra_t, dec_t, frame='icrs', unit='deg')
    aa_frame = coord.AltAz(obstime = t_utc, location = LOC)
    c_altaz  = c.transform_to(aa_frame)
    az = c_altaz.az.deg.copy()
    az[az > 180.] = az[az > 180.] - 360.
    el  = c_altaz.alt.deg
    
    # Set up array of days (expand 1 day beyond range in both directions):
    days_mjd = np.arange(-1.0, 1.0, 1.0)
    days_utc = Time(start_date, format="iso", scale="utc") + days_mjd

    # Set up observer object and populate:
    obs = ephem.Observer()
    obs.lon  = str(LOC.geodetic.lon.deg) #Note that lon should be string
    obs.lat  = str(LOC.geodetic.lat.deg) #Note that lat should be string
    obs.elev = LOC.geodetic.height.value

    # Loop to record sunrises and sunsets:
    sunrise_list = []
    sunset_list  = []
    for i in range(0,len(days_utc)):

        obs.date = str(days_utc[i])
        sunrise = obs.next_rising(ephem.Sun()).datetime()
        sunrise_list.append(sunrise)

        obs.date = str(days_utc[i])
        sunset = obs.next_setting(ephem.Sun()).datetime()
        sunset_list.append(sunset)

    idx_count = np.where((Time(t_utc).mjd>Time(sunset_list[0]).mjd) & 
                            (Time(t_utc).mjd<Time(sunrise_list[1]).mjd) & 
                            (el>15))[0]
    hrs = (Time(t_utc[idx_count[-1]]).mjd - Time(t_utc[idx_count[0]]).mjd)*24.

    return hrs

def el_vs_time(ra_t, dec_t, day):

    ##### Constants - eventually convert to inputs ####
    Ndays  =  5.0 # days
    dt =  30.0/60. # hours

    start_date = Time(day).iso

    ##### 1) Data for tracking the target #####

    # Set up time array:
    dmjd_arr = np.arange(0, Ndays+1+dt/24., dt/24.)
    t_utc = Time(start_date, format="iso", scale="utc") + dmjd_arr

    # Get alt/az coords of target vs time:
    c = coord.SkyCoord(ra_t, dec_t, frame='icrs', unit='deg')
    aa_frame = coord.AltAz(obstime = t_utc, location = LOC)
    c_altaz  = c.transform_to(aa_frame)
    az = c_altaz.az.deg.copy()
    az[az > 180.] = az[az > 180.] - 360.
    el  = c_altaz.alt.deg

    ##### 2) Data for tracking sunrise/sunset #####
    
    # Set up array of days (expand 1 day beyond range in both directions):
    days_mjd = np.arange(-1.0, Ndays+1.0, 1.0)
    days_utc = Time(start_date, format="iso", scale="utc") + days_mjd

    # Set up observer object and populate:
    obs = ephem.Observer()
    obs.lon  = str(LOC.geodetic.lon.deg) #Note that lon should be string
    obs.lat  = str(LOC.geodetic.lat.deg) #Note that lat should be string
    obs.elev = LOC.geodetic.height.value

    # Loop through days to get sunrise and sunset times:
    sunrise_list = []
    sunset_list  = []
    hrs   = []
    #data['days_utc'] = days_utc[1:-1]

    # Loop to record sunrises and sunsets:
    for i in range(0,len(days_utc)):

        obs.date = str(days_utc[i])
        sunrise = obs.next_rising(ephem.Sun()).datetime()
        sunrise_list.append(sunrise)

        obs.date = str(days_utc[i])
        sunset = obs.next_setting(ephem.Sun()).datetime()
        sunset_list.append(sunset)

    # Loop to count hours of night-time:
    for i in range(1,len(days_utc)-1):
        idx_count = np.where((Time(t_utc).mjd>Time(sunset_list[i]).mjd) & 
                             (Time(t_utc).mjd<Time(sunrise_list[i+1]).mjd) & 
                             (el>15))[0]
        hrs.append((Time(t_utc[idx_count[-1]]).mjd - Time(t_utc[idx_count[0]]).mjd)*24.)

    #print(hrs)
    
    return t_utc, el, sunrise_list, sunset_list
