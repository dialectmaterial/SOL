"""Compatibility import for research surfaces using the installed projection."""
import sys
from sol.reader import surface as _surface

sys.modules[__name__] = _surface
