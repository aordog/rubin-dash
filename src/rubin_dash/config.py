"""Configuration for rubin-dash."""

from datetime import datetime, timedelta
from pathlib import Path

PORT = 5000 # Server
DEFAULT_USER_ID: int  = 1  # User ID: revisit this when adding users
REFRESH_INTERVAL: int = 30 # refresh rate for simulated iterations
SIM_START = datetime(2025, 8, 20)  # simulated days start
SIM_END   = datetime(2025, 11, 30) # simulated days end
VERBOSE = False  # Show debug columns in table (row_id, gr_name, gr_num, mem_num)

QUERY_FILE     = "small_query.txt" # File with user-selected targets
INITIAL_OFFSET = 0.0               # declination limit to filter targets

# Output directory for resource-tracking files and logs:
OUTPUT_BASE = Path("/home/aordog/Dropbox/candiapl/rubin-dash-out/")

# Make the list of simulated dates:
def simulation_dates() -> list[str]:
    """Return the full list of YYYY-MM-DD strings for the sim window."""
    n_days = (SIM_END - SIM_START).days + 1
    return [
        (SIM_START + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(n_days)
    ]