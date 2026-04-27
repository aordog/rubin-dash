"""
config.py: Configuration parameters for the Rubin Dashboard.

Defines user inputs, server settings, simulation parameters, and stress
testing configuration. Constants are organized by category with inline
comments explaining their purpose.

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
REFRESH_INTERVAL: int = 30 # refresh rate for simulated iterations
SIM_START = datetime(2025, 8, 20)  # simulated days start
SIM_END   = datetime(2025, 11, 30) # simulated days end
VERBOSE = False  # Show debug columns in table (gr_name, gr_num, mem_num)

# Stress testing
MEM_TEST_MODE = False  # Turn on memory stress testing (simulated clicks)
STRESS_TEST_CLICK_INTERVAL = 3  # Seconds between automated clicks