"""
core.py

**Author:** Anna Ordog

"""

import rubin_dash.utils as utils


class MetaData:
    """A base class for reading in meta data.

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
    
    """

    def __init__(self, date:str, ra_t:float, dec_t:float, r_ang:float,
                 description: str = "Metadata Access"):
        self.description = description
        self.date  = date
        self.ra_t  = ra_t
        self.dec_t = dec_t
        self.r_ang = r_ang

class RubinScheduleViewer(MetaData):
    """A class for reading in meta data from the Rubin Schedule Viewer.

    This class reads in metadata from the Rubin Schedule Viewer, which is
    currently missing the camera angle data. Thus, using this method for
    now will not give the correct shapes of masks in the 2D mapping of visits
    coverage. NOTE: for now the radial distance needs to be smaller than half of
    the LSSTCam FOV width to ensure the target is within all visits read in.

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
    """
    
    def __init__(self, date: str, ra_t: float, dec_t: float, r_ang: float):
        super().__init__(date, ra_t, dec_t, r_ang, description="Rubin Schedule Viewer reader")

    def get_metadata_rsv(self) -> dict:
        """Read in meta data from the Rubin Schedule Viewer using input parameters."""
        
        return utils.get_metadata_rsv(self.date, self.ra_t, self.dec_t, self.r_ang)



        