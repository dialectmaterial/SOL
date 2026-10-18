"""Start the ESSENCE interface: python -m sol.essence.tui --context FILE."""
from __future__ import annotations

import argparse
import sys

from sol.essence.tui import TEXTUAL_HINT, textual_available
from sol.essence.tui.context import read_context


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="python -m sol.essence.tui", description=__doc__)
    parser.add_argument("--context", required=True, help="private context file written by the reader")
    options = parser.parse_args(arguments)
    if not textual_available():
        print(f"sol: {TEXTUAL_HINT}", file=sys.stderr)
        return 2
    try:
        context = read_context(options.context)
    except (OSError, ValueError) as error:
        print(f"sol: cannot open ESSENCE: {error}", file=sys.stderr)
        return 2
    from sol.essence.tui.app import EssenceApp
    return EssenceApp(context).run() or 0


if __name__ == "__main__":
    raise SystemExit(main())
