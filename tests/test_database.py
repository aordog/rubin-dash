"""Test database utility functions for rubin-dash.

Tests coordinate filtering, spatial grouping, and grid generation
used in database initialization.
"""

import pytest
import numpy as np
import healpy as hp

from rubin_dash.database import _group_targets, _add_mask_grid


class TestGroupTargets:
    """Test HEALPix-based target grouping."""

    def test_group_targets_basic(self):
        """Test basic target grouping."""
        ra = np.array([0.0, 1.0, 180.0, 181.0])
        dec = np.array([0.0, 0.0, 0.0, 0.0])
        nside = 4

        groups = _group_targets(ra, dec, nside)

        # Should have at least 2 groups (targets on opposite sides of sky)
        assert len(groups) >= 2

        # Each group should have required keys
        for group in groups:
            assert 'name_gr' in group
            assert 'ra_gr' in group
            assert 'dec_gr' in group
            assert 'ra_mem' in group
            assert 'dec_mem' in group

    def test_group_targets_all_same_location(self):
        """Test grouping when all targets are at same location."""
        ra = np.array([45.0, 45.0, 45.0])
        dec = np.array([30.0, 30.0, 30.0])
        nside = 4

        groups = _group_targets(ra, dec, nside)

        # Should have exactly 1 group
        assert len(groups) == 1
        # Group should contain all 3 members
        assert len(groups[0]['ra_mem']) == 3
        assert len(groups[0]['dec_mem']) == 3

    def test_group_targets_preserves_coordinates(self):
        """Test that grouping preserves original coordinates."""
        ra = np.array([10.0, 20.0, 30.0])
        dec = np.array([-20.0, -10.0, 0.0])
        nside = 4

        groups = _group_targets(ra, dec, nside)

        # Collect all member coordinates
        all_ra = np.concatenate([g['ra_mem'] for g in groups])
        all_dec = np.concatenate([g['dec_mem'] for g in groups])

        # Should have same coordinates (possibly reordered)
        assert np.allclose(sorted(all_ra), sorted(ra))
        assert np.allclose(sorted(all_dec), sorted(dec))

    def test_group_targets_nside_effect(self):
        """Test that higher nside creates more groups."""
        ra = np.linspace(0, 180, 20)
        dec = np.linspace(-60, 60, 20)

        groups_low = _group_targets(ra, dec, nside=4)
        groups_high = _group_targets(ra, dec, nside=16)

        # Higher nside should create more groups
        assert len(groups_high) >= len(groups_low)


class TestAddMaskGrid:
    """Test spatial grid generation for 2D mask computation."""

    def test_add_mask_grid_basic(self):
        """Test basic grid generation."""
        ra_center = 45.0
        dec_center = 30.0

        ra_grid, dec_grid = _add_mask_grid(ra_center, dec_center)

        # Should return arrays
        assert isinstance(ra_grid, np.ndarray)
        assert isinstance(dec_grid, np.ndarray)
        # Should have same length
        assert len(ra_grid) == len(dec_grid)
        # Should have reasonable number of points
        assert len(ra_grid) > 100

    def test_add_mask_grid_centered(self):
        """Test that grid is roughly centered on pointing."""
        ra_center = 90.0
        dec_center = 45.0

        ra_grid, dec_grid = _add_mask_grid(ra_center, dec_center)

        # Grid should be roughly centered (within ~3 degrees)
        assert abs(np.mean(ra_grid) - ra_center) < 3.0
        assert abs(np.mean(dec_grid) - dec_center) < 3.0

    def test_add_mask_grid_bounds(self):
        """Test that grid stays within reasonable bounds."""
        ra_center = 180.0
        dec_center = 0.0

        ra_grid, dec_grid = _add_mask_grid(ra_center, dec_center)

        # Grid should be within ~3 degrees of center
        assert np.all(np.abs(ra_grid - ra_center) < 3.0)
        assert np.all(np.abs(dec_grid - dec_center) < 3.0)

    def test_add_mask_grid_different_centers(self):
        """Test grid generation at different sky positions."""
        positions = [
            (0.0, 0.0),
            (90.0, 45.0),
            (180.0, -30.0),
            (270.0, -60.0),
        ]

        for ra_center, dec_center in positions:
            ra_grid, dec_grid = _add_mask_grid(ra_center, dec_center)
            # Should always produce valid grids
            assert len(ra_grid) > 0
            assert len(dec_grid) > 0
            assert len(ra_grid) == len(dec_grid)