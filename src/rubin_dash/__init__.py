"""rubin-dash: interactive survey-progress dashboard for Rubin LSST."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("rubin-dash")
except PackageNotFoundError:
    __version__ = "0.0.0dev"

__author__ = "Anna Ordog"