"""
core.py: Core data classes and functions for Rubin Dashboard

This module provides the main data classes for managing data, plots, and 
logging within the Rubin LSST dashboard application.

**Author:** Anna Ordog, for CanDIAPL

Classes
-------
BasePlot
    Base class for plot formatting and display.
QuietFilter
    Logging filter to suppress noisy output from specific endpoints.
Logger
    Logging handler for writing to terminal and log file.
TableData
    Manages summary table data for display.
TargetMap
    Manages 2D visits coverage maps for groups of targets.
TargetTimeSeries
    Manages time series visits data for individual targets.
ObservabilityData
    Manages future observability predictions for targets.

Functions
---------
initialize_tracking
    Set up database and load target data for tracking.
populate_database
    Process visits and mask data for all target groups.
"""

import rubin_dash.utils as utils
import logging

BANDS = ('u', 'g', 'r', 'i', 'z', 'y')


class QuietFilter(logging.Filter):
    """Logging filter to suppress verbose Flask endpoint messages.
    
    Filters out logging records from endpoints that generate high-cadence
    messages not useful for debugging or monitoring to keep log files and 
    terminal output readable.
    
    Attributes
    ----------
    NOISY : set
        Collection of endpoint paths whose log messages should be suppressed.
    """

    NOISY = {'/check_update', '/next_update'}

    def filter(self, record):
        """Check if a log record should be allowed.
        
        Parameters
        ----------
        record : logging.LogRecord
            The log record to filter.
        
        Returns
        -------
        bool
            False if the record contains a message from a noisy endpoint,
            True otherwise.
        """
        return not any(path in record.getMessage() for path in self.NOISY)


class Logger:
    """Multi-destination logging handler with timestamp prefixing.
    
    Writes log messages to multiple output streams (terminal, file) with
    timestamps. Compatible with sys.stdout/sys.stderr redirection.
    
    Parameters
    ----------
    *destinations : file-like
        Variable number of output streams to write to (e.g., sys.stdout,
        open file objects).
    
    Attributes
    ----------
    destinations : tuple
        Collection of output streams.
    at_line_start : bool
        Flag tracking start of new line (for timestamp insertion).
    """
    
    def __init__(self, *destinations):
        self.destinations = destinations
        self.at_line_start = True

    def write(self, msg):
        """Write to all destinations with timestamp prefixing.
        
        Parameters
        ----------
        msg : str
            The message to write.
        """
        self.at_line_start = utils.write(
            self.destinations, msg, self.at_line_start
        )

    def flush(self):
        """Flush all output streams."""
        for dest in self.destinations:
            dest.flush()

