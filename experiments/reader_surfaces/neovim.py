"""Checkout experiments reuse the optional installed Neovim host."""
import sys
from sol.terminal import neovim as _neovim

sys.modules[__name__] = _neovim
