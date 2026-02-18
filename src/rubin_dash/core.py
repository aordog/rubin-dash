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


class BasePlot:
    """A base class for formatting the plots."""

    def __init__(self, description: str = "Base Plot"):
        self.description = description


class VisitsMap(BasePlot):
    """A class for making the 2D visits map."""

    def __init__(self, target: Target):
        super().__init__(description="2D visits map")
        self.target = target

    def visits_maps(self, date):
        """Make the 2D map of visits to date for selected target"""

        return utils.visits_maps(self.target, date)


class Dashboard:

    def __init__(self, date:str, ra_t:float, dec_t:float,
                 fig1_html:str, fig2_html:str, fig3_html:str, file_out:str,
                 description: str = "Build Dashboard"):
        self.description = description
        self.date  = date
        self.ra_t  = ra_t
        self.dec_t = dec_t
        self.fig1_html = fig1_html
        self.fig2_html = fig2_html
        self.fig3_html = fig3_html
        self.file_out  = file_out

    def build_html(self):
        return utils.build_html(self.date, self.ra_t, self.dec_t, 
                                self.fig1_html, self.fig2_html, 
                                self.fig3_html, self.file_out)
    

"""
## WORK ON THIS NEXT WEEK TO FIGURE OUT HOW TO MAKE DASHBOARD IN ONE GO
def main(date: str, ra_t: float, dec_t: float, r_ang: float):

    print('-----------------------------')
    print('Making dashboard up to '+date)

    rsv = RubinScheduleViewer(date, ra_t, dec_t, r_ang)
    metadata = rsv.get_metadata_rsv()

    print(metadata['ra'])
    print(len(metadata['ra']) + ' observations today.')

    target_plots = SingleTargetPlotting(date, ra_t, dec_t, r_ang, metadata)
    fig_html = target_plots.visits_maps()

    dash = BuildDashboard(date, ra_t, dec_t, fig_html, fig_html, fig_html, 'new_file.html')
    dash.build_html()
    print('-----------------------------')

    return
    

# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    main()

"""