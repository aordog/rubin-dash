"""
config.py: Configuration file for Rubin Dashboard.

This config file contains the basic parameters for running the dashboard app. 

**Author:** Anna Ordog, for CanDIAPL

"""

from datetime import datetime, timedelta
from pathlib import Path

########### USER INPUTS #########
QUERY_FILE     = "small_query.txt" # File with user-selected targets
INITIAL_OFFSET = 0.0               # declination limit to filter targets
#################################

# Server-side info
PORT = 5000 # Server
DEFAULT_USER_ID: int  = 1  # User ID. TO DO: REVISIT WHEN ADDING USERS!
DB_NAME = "lsst_database"
OUTPUT_BASE = Path("/home/aordog/Dropbox/candiapl/rubin-dash-out/")

# Simulated LSST survey (for testing)
REFRESH_INTERVAL: int = 20 # refresh rate for simulated iterations
SIM_START = datetime(2025, 8, 20)  # simulated days start
SIM_END   = datetime(2025, 11, 30) # simulated days end
VERBOSE = False  # Show debug columns in table (gr_name, gr_num, mem_num)

# Stress testing
MEM_TEST_MODE = True  # Turn on memory stress testing (simulated clicks)
STRESS_TEST_CLICK_INTERVAL = 3  # Seconds between automated clicks

# Make the list of simulated dates:
def simulation_dates() -> list[str]:
    """Return the full list of YYYY-MM-DD strings for the sim window."""
    n_days = (SIM_END - SIM_START).days + 1
    return [
        (SIM_START + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(n_days)
    ]