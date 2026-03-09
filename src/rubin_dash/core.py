"""
core.py

**Author:** Anna Ordog

"""

import rubin_dash.utils as utils
import pandas as pd


class Target:
    """A class for information pertaining to a single target.

    Parameters
    ----------
    ra_t : float
        The right ascension of the target position (in degrees).
    dec_t : float
        The declination of the target position (in degrees).
    r : float
        The radial distance from the target to search for visits.
    name : string
        Optional name for the target.
    data :  dictionary
        The visits (meta)data gathered from the database for this target.
        The methods for the Target class serve to populate this dictionary.
    """

    def __init__(self, ra_t:float, dec_t:float, r:float, name:str, 
                 description: str = "Target Specifics"):
        self.description = description
        self.ra_t  = ra_t
        self.dec_t = dec_t
        self.r = r
        self.name = name
        self.ra_grid, self.dec_grid = utils.add_mask_grid(ra_t, dec_t, r)
        self.data: dict | None = None

    def get_metadata_rsv(self, date) -> dict:

        """Read in metadata from the Rubin Schedule Viewer.

        This function reads in metadata from the Rubin Schedule Viewer (RSV),
        then makes daily and cumulative masks based on the LSST camera, and 
        counts the number of daily and cumulative visits at the target
        location. ***Note: RSV is missing the camera angle and band data. 
        Thus, using this method for now will not give the correct shapes of 
        masks in the 2D mapping of visits coverage (fake camera angles are 
        used) and the displayed band information is also not correct (randomly 
        selected).
        
        Parameters
        ----------
        date : float
            The date (in ISO format) for which to read in the metadata.
        """
        
        self.data = utils.get_metadata_rsv(date, self.ra_t, self.dec_t,
                                           self.r, self.data)
        self.data = utils.lsstcam_mask(date, self.ra_grid, self.dec_grid, 
                                       self.data)
        self.data = utils.count_target_visits(date, self.ra_t, self.dec_t,
                                              self.ra_grid, self.dec_grid, 
                                              self.data)
        
    def get_metadata_ppdb(self, date) -> dict:

        """Read in meta data from the Prompt Products Database.

        This function reads in metadata from the Prompt Products Database,
        expected to become available later in 2026.
        
        Parameters
        ----------
        date : float
            The date (in ISO format) for which to read in the metadata.
        """
        pass

    def get_metadata_consdb(self, date) -> dict:

        """Read in meta data from the Consolidated Database

        This function reads in metadata from the Consolidated Database,
        expected to become available later in 2026.
        
        Parameters
        ----------
        date : float
            The date (in ISO format) for which to read in the metadata.
        """
        pass



class SummaryTable:
    """A class for assembling the targets into a table.

    Parameters
    ----------
    target_set : list
        The list of Target objects.
    """

    def __init__(self, target_set:list,
                 description: str = "Summary of all targets"):
        self.description = description
        self.target_set  = target_set

    def make_table(self) -> pd.DataFrame:

        return utils.make_table(self.target_set)



class BasePlot:
    """A base class for formatting the plots."""

    def __init__(self, description: str = "Base Plot"):
        self.description = description


class VisitsFigures(BasePlot):
    """A class for making visits figures."""

    def __init__(self, target: Target):
        super().__init__(description="2D visits map")
        self.target = target

    def visits_maps(self, date, maptype):
        """Make the 2D map of visits to date for selected target"""

        return utils.visits_maps(self.target, date, maptype)
    
    def visits_plots(self, maptype):
        """Make the plot of visits versus time for selected target"""

        return utils.visits_plots(self.target, maptype)
    
    def make_long_forecast_plot(self, date):
        """Make the longterm forecast plot"""

        return utils.make_long_forecast_plot(date, self.target.ra_t, self.target.dec_t)
