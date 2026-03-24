"""
core.py

**Author:** Anna Ordog

"""

import rubin_dash.utils as utils
import pandas as pd
import numpy as np
import psycopg2 # note: pip install psycopg2-binary
import psycopg2.extras
import json


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

    def __init__(self, group: dict, 
                 description: str = "Target group specifics"):
        self.description = description
        self.ra_gr   = group['ra_gr']
        self.dec_gr  = group['dec_gr']
        self.name_gr = group['name_gr']
        self.ra_mem  = group['ra_mem']
        self.dec_mem = group['dec_mem']
        self.ra_grid, self.dec_grid = utils.add_mask_grid(group['ra_gr'], 
                                                          group['dec_gr'])
        self.data: dict | None = None
        self.data = utils.initialize_data_dict(self.data)

    def get_metadata_rsv(self, visits) -> dict:

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
        
        return utils.get_metadata_rsv(visits, self.ra_gr, self.dec_gr)
    
    def lsstcam_mask(self, visits_use, camera) -> dict:

        self.data = utils.lsstcam_mask(visits_use, camera,
                                       self.ra_grid, self.dec_grid, self.data)
        
    def count_target_visits(self, date) -> dict:
        self.data = utils.count_target_visits(date, self.ra_mem, self.dec_mem,
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


class Target2:
    """A class for information pertaining to a single target.
    """

    def __init__(self, target_id: int, conn, 
                 description: str = "Target group specifics"):
        self.description = description
        self.conn = conn
        self.target_id = target_id

        # Load static data from DB
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
                    SELECT name_gr, ra_gr, dec_gr, ra_mem, dec_mem, ra_grid, dec_grid
                    FROM targets WHERE target_id = %s
                    """, (target_id,))
        row = cur.fetchone()

        self.ra_gr   = row['ra_gr']
        self.dec_gr  = row['dec_gr']
        self.name_gr = row['name_gr']
        self.ra_mem  = np.array(row['ra_mem'])
        self.dec_mem = np.array(row['dec_mem'])
        self.ra_grid = np.array(row['ra_grid'])
        self.dec_grid = np.array(row['dec_grid'])

        self.data: dict | None = None
        self.data = utils.initialize_data_dict(self.data)

        # Load existing mask state from DB (if any previous days ran)
        self._load_mask_state()

    def _load_mask_state(self):
        """Load latest/total masks from DB into self.data."""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT latest, total FROM target_mask_state
            WHERE target_id = %s
        """, (self.target_id,))
        row = cur.fetchone()
        if row and row['latest']:
            for band in ('umask', 'gmask', 'rmask', 'imask', 'zmask', 'ymask'):
                self.data['latest'][band] = np.array(row['latest'][band])
                self.data['total'][band]  = np.array(row['total'][band])

    def _save_mask_state(self):
        """Persist latest/total masks to DB."""
        latest = {b: self.data['latest'][b].tolist() for b in
                  ('umask', 'gmask', 'rmask', 'imask', 'zmask', 'ymask')}
        total  = {b: self.data['total'][b].tolist() for b in
                  ('umask', 'gmask', 'rmask', 'imask', 'zmask', 'ymask')}
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO target_mask_state (target_id, updated_at, latest, total)
            VALUES (%s, NOW(), %s, %s)
            ON CONFLICT (target_id) DO UPDATE SET
                updated_at = NOW(),
                latest = EXCLUDED.latest,
                total  = EXCLUDED.total
        """, (self.target_id, json.dumps(latest), json.dumps(total)))
        self.conn.commit()

    def _save_daily_visits(self, date):
        """Write today's 6 visit arrays to the hypertable, then free memory."""
        today = self.data['daily'][date]
        n_members = len(self.ra_mem)
        rows = [
            (date, self.target_id, i,
             float(today['uvisits'][i]), float(today['gvisits'][i]),
             float(today['rvisits'][i]), float(today['ivisits'][i]),
             float(today['zvisits'][i]), float(today['yvisits'][i]))
            for i in range(n_members)
        ]
        psycopg2.extras.execute_values(
            self.conn.cursor(),
            """INSERT INTO target_daily_visits
               (time, target_id, member_idx,
                u_visits, g_visits, r_visits, i_visits, z_visits, y_visits)
               VALUES %s""",
            rows, page_size=5000
        )
        self.conn.commit()

        # Free memory — this is the key line
        del self.data['daily'][date]

    def get_metadata_rsv(self, visits) -> dict:

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
        
        return utils.get_metadata_rsv(visits, self.ra_gr, self.dec_gr)
    
    def lsstcam_mask(self, visits_use, camera) -> dict:

        self.data = utils.lsstcam_mask(visits_use, camera,
                                       self.ra_grid, self.dec_grid, self.data)
        
    def count_target_visits(self, date) -> dict:
        self.data = utils.count_target_visits(date, self.ra_mem, self.dec_mem,
                                              self.ra_grid, self.dec_grid, 
                                              self.data)
        
    def summary_row(self):
        """Return a lightweight dict with everything SummaryTable needs.
        Adapt the keys to match what your SummaryTable expects."""
        return {
            'target_id': self.target_id,
            'name_gr':   self.name_gr,
            'ra_gr':     self.ra_gr,
            'dec_gr':    self.dec_gr,
            'ra_mem':    self.ra_mem,
            'dec_mem':   self.dec_mem,
            # add whatever other scalars SummaryTable reads
        }


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

    def visits_maps(self, idx_mem, date, maptype):
        """Make the 2D map of visits to date for selected target"""

        return utils.visits_maps(self.target, idx_mem, date, maptype)
    
    def visits_plots(self, member, maptype):
        """Make the plot of visits versus time for selected target"""

        return utils.visits_plots(self.target, member, maptype)
    
    def make_long_forecast_plot(self, member, date):
        """Make the longterm forecast plot"""

        return utils.make_long_forecast_plot(date, 
                                             self.target.ra_mem[member], 
                                             self.target.dec_mem[member])
