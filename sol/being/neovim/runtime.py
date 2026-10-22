"""Location of the installer's private editor; no downloads during reading."""
import os
from pathlib import Path

NEOVIM_VERSION = "0.11.6"


def managed_neovim():
    value = os.environ.get("XDG_DATA_HOME")
    base = Path(value).expanduser() if value else Path.home() / ".local" / "share"
    if not base.is_absolute():
        raise ValueError("XDG_DATA_HOME must be an absolute directory")
    return base / "sol" / "runtime" / f"neovim-{NEOVIM_VERSION}" / "bin" / "nvim"
