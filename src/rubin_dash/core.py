"""
core.py

**Author:** Anna Ordog

"""

import rubin_dash.utils as utils
import pandas as pd


class Target:
    """A class for info pertaining to a single target.

    Parameters
    ----------
    ra_t : float
        The right ascension of the target position (in degrees).
    dec_t : float
        The declination of the target position (in degrees).
    r_ang : float
        The radial distance from the target to search for visits.
    name : string
        Optional name for the target.
    """

    def __init__(self, ra_t:float, dec_t:float, r:float, name:str, 
                 description: str = "Target Specifics"):
        self.description = description
        self.ra_t  = ra_t
        self.dec_t = dec_t
        self.r = r
        self.name = name 
        self.data: dict | None = None

    def get_metadata_rsv(self, date) -> dict:

        """Read in meta data from the Rubin Schedule Viewer.

        This function reads in metadata from the Rubin Schedule Viewer, which 
        is currently missing the camera angle data. Thus, using this method 
        for now will not give the correct shapes of masks in the 2D mapping of 
        visits coverage. Note: for now the radial distance needs to be smaller 
        than half of the LSSTCam FOV width to ensure the target is within all 
        visits read in.
        
        Parameters
        ----------
        date : float
            The date (in ISO format) for which to read in the data.
        """
        
        self.data = utils.get_metadata_rsv(date, self.ra_t, self.dec_t,
                                           self.r, self.data)
        
    def get_metadata_ppdb(self, date) -> dict:

        """Read in meta data from the Prompt Products Database"""
        pass

    def get_metadata_consdb(self, date) -> dict:

        """Read in meta data from the Consolidated Database"""
        pass

    def add_mask_grid(self):

        self.ra_grid, self.dec_grid = utils.add_mask_grid(self.ra_t, self.dec_t, self.r)

    def lsstcam_mask(self,date):

        self.data = utils.lsstcam_mask(date, self.ra_grid, self.dec_grid, self.data)

    def count_target_visits(self,date):

        self.data = utils.count_target_visits(date, self.ra_t, self.dec_t,
                                              self.ra_grid, self.dec_grid, self.data)


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


class Dashboard:

    def __init__(self, date:str, ra_t:float, dec_t:float,
                 fig1_html:str, fig2_html:str, fig3_html:str, 
                 table:pd.DataFrame, file_out:str,
                 description: str = "Build Dashboard"):
        self.description = description
        self.date  = date
        self.ra_t  = ra_t
        self.dec_t = dec_t
        self.fig1_html = fig1_html
        self.fig2_html = fig2_html
        self.fig3_html = fig3_html
        self.table = table
        self.file_out  = file_out

    def build_html(self):
        return utils.build_html(self.date, self.ra_t, self.dec_t, 
                                self.fig1_html, self.fig2_html, 
                                self.fig3_html, 
                                self.table, self.file_out)
    