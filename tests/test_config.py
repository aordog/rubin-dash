"""Test configuration module for rubin-dash.

Verifies that configuration parameters are properly defined and
have reasonable values.
"""

import pytest
from datetime import datetime

from rubin_dash.config import (
    PORT,
    DEFAULT_USER_ID,
    QUERY_TYPE,
    REFRESH_INTERVAL,
    SIM_START,
    SIM_END,
    DAYS_FORECAST,
    MEM_TEST_MODE,
)


class TestConfigValues:
    """Test that configuration values are reasonable."""

    def test_port_is_valid(self):
        """Test that PORT is a valid port number."""
        assert isinstance(PORT, int)
        assert 1024 <= PORT <= 65535

    def test_user_id_is_positive(self):
        """Test that DEFAULT_USER_ID is positive."""
        assert isinstance(DEFAULT_USER_ID, int)
        assert DEFAULT_USER_ID > 0

    def test_query_type_is_valid(self):
        """Test that QUERY_TYPE is one of the supported options."""
        assert QUERY_TYPE in ['SIM', 'RSV']

    def test_refresh_interval_is_positive(self):
        """Test that REFRESH_INTERVAL is positive."""
        assert isinstance(REFRESH_INTERVAL, int)
        assert REFRESH_INTERVAL > 0

    def test_sim_dates_are_ordered(self):
        """Test that simulation start is before end."""
        assert isinstance(SIM_START, datetime)
        assert isinstance(SIM_END, datetime)
        assert SIM_START < SIM_END

    def test_days_forecast_is_positive(self):
        """Test that DAYS_FORECAST is positive."""
        assert isinstance(DAYS_FORECAST, int)
        assert DAYS_FORECAST > 0

    def test_mem_test_mode_is_bool(self):
        """Test that MEM_TEST_MODE is a boolean."""
        assert isinstance(MEM_TEST_MODE, bool)