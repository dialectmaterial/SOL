"""Start the ESSENCE interface: python -m sol.essence.tui --context FILE."""
from __future__ import annotations

import argparse
import sys

from sol.essence.tui import TEXTUAL_HINT, textual_available
from sol.essence.tui.context import read_context
from sol.reader.options import DEFAULT_READER_THEME, READER_THEMES


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="python -m sol.essence.tui", description=__doc__)
    parser.add_argument("--context", required=True, help="private context file written by the reader")
    parser.add_argument("--theme", choices=READER_THEMES, default=DEFAULT_READER_THEME,
                        help="the reader's theme, which ESSENCE follows")
    parser.add_argument("--theme-file", help="private file the reader rewrites when its theme changes")
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
    return EssenceApp(context, theme=options.theme, theme_file=options.theme_file).run() or 0


if __name__ == "__main__":
    raise SystemExit(main())
