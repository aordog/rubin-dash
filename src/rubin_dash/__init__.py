from . import utils
from .core import TargetMap
#from .test import test

try:
    from ._version import version as __version__  # noqa
except ImportError:
    __version__ = "0.0.0dev"

__author__ = "Anna Ordog"

# List packages here to explicitly define the public API. Now candiamazing.<package> works.
__all__ = (
    "RubinScheduleViewer",
    "utils",
    "test",
    "__version__",
    "__author__",
)