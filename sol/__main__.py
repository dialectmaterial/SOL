"""Support `python -m sol` from an installation or the checkout."""

from . import cli

if __name__ == "__main__":
    raise SystemExit(cli())
