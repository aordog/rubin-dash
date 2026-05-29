"""Test the utility functions for rubin-dash.

Tests helper functions for date conversion, coordinate filtering,
and fake data generation used in prototyping.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from rubin_dash.utils import (
    remove_high_dec,
    make_fake_bands,
    make_fake_rot,
    simulation_dates,
    date_to_nightnum,
)


class TestRemoveHighDec:
    """Test declination filtering."""

    def test_remove_high_dec_basic(self):
        """Test basic declination filtering."""
        ra = np.array([0.0, 90.0, 180.0, 270.0])
        dec = np.array([-30.0, 0.0, 30.0, 60.0])
        dec_lim = 45.0

        ra_out, dec_out = remove_high_dec(ra, dec, dec_lim)

        assert len(ra_out) == 3
        assert len(dec_out) == 3
        assert np.all(dec_out < dec_lim)
        assert np.allclose(dec_out, [-30.0, 0.0, 30.0])

    def test_remove_high_dec_all_removed(self):
        """Test when all sources exceed declination limit."""
        ra = np.array([0.0, 90.0])
        dec = np.array([60.0, 70.0])
        dec_lim = 45.0

        ra_out, dec_out = remove_high_dec(ra, dec, dec_lim)

        assert len(ra_out) == 0
        assert len(dec_out) == 0

    def test_remove_high_dec_none_removed(self):
        """Test when no sources exceed declination limit."""
        ra = np.array([0.0, 90.0, 180.0])
        dec = np.array([-30.0, 0.0, 30.0])
        dec_lim = 45.0

        ra_out, dec_out = remove_high_dec(ra, dec, dec_lim)

        assert len(ra_out) == 3
        assert len(dec_out) == 3
        assert np.allclose(ra_out, ra)
        assert np.allclose(dec_out, dec)


class TestFakeBands:
    """Test fake filter band generation."""

    def test_make_fake_bands_length(self):
        """Test that correct number of bands are generated."""
        for n in [1, 5, 10, 100]:
            bands = make_fake_bands(n)
            assert len(bands) == n

    def test_make_fake_bands_valid(self):
        """Test that generated bands are valid LSST filters."""
        valid_bands = {'u', 'g', 'r', 'i', 'z', 'y'}
        bands = make_fake_bands(50)
        assert all(b in valid_bands for b in bands)

    def test_make_fake_bands_empty(self):
        """Test edge case of zero visits."""
        bands = make_fake_bands(0)
        assert len(bands) == 0


class TestFakeRotation:
    """Test fake camera rotation angle generation."""

    def test_make_fake_rot_length(self):
        """Test that correct number of rotation angles are generated."""
        for n in [1, 5, 10, 100]:
            rots = make_fake_rot(n)
            assert len(rots) == n

    def test_make_fake_rot_range(self):
        """Test that rotation angles are in valid range [0, 90)."""
        rots = make_fake_rot(100)
        assert all(0 <= r < 90 for r in rots)

    def test_make_fake_rot_empty(self):
        """Test edge case of zero visits."""
        rots = make_fake_rot(0)
        assert len(rots) == 0


class TestSimulationDates:
    """Test date range generation."""

    def test_simulation_dates_basic(self):
        """Test basic date range generation."""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 5)

        dates = simulation_dates(start, end)

        assert len(dates) == 5
        assert dates[0] == "2025-01-01"
        assert dates[-1] == "2025-01-05"

    def test_simulation_dates_single_day(self):
        """Test single day range."""
        start = datetime(2025, 6, 15)
        end = datetime(2025, 6, 15)

        dates = simulation_dates(start, end)

        assert len(dates) == 1
        assert dates[0] == "2025-06-15"

    def test_simulation_dates_format(self):
        """Test that dates are in ISO format."""
        start = datetime(2025, 3, 1)
        end = datetime(2025, 3, 3)

        dates = simulation_dates(start, end)

        for date_str in dates:
            # Should be parseable as ISO format
            parts = date_str.split('-')
            assert len(parts) == 3
            assert len(parts[0]) == 4  # year
            assert len(parts[1]) == 2  # month
            assert len(parts[2]) == 2  # day


class TestDateToNightnum:
    """Test date to night number conversion."""

    def test_date_to_nightnum_basic(self):
        """Test basic date to night number conversion."""
        base_mjd = 60000.0
        date = "2025-01-01"

        nightnum = date_to_nightnum(date, base_mjd)

        # Should return an integer
        assert isinstance(nightnum, (int, np.integer))
        # Should be non-negative for dates after base
        assert nightnum >= 0

    def test_date_to_nightnum_consistency(self):
        """Test that same date always gives same night number."""
        base_mjd = 60000.0
        date = "2025-06-15"

        nightnum1 = date_to_nightnum(date, base_mjd)
        nightnum2 = date_to_nightnum(date, base_mjd)

        assert nightnum1 == nightnum2

    def test_date_to_nightnum_ordering(self):
        """Test that later dates give higher night numbers."""
        base_mjd = 60000.0
        date1 = "2025-01-01"
        date2 = "2025-01-02"
        date3 = "2025-01-10"

        n1 = date_to_nightnum(date1, base_mjd)
        n2 = date_to_nightnum(date2, base_mjd)
        n3 = date_to_nightnum(date3, base_mjd)

        assert n1 < n2 < n3