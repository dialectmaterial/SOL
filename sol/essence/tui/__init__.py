"""ESSENCE's Textual interface (optional extra `sol-organizes-logic[essence]`).

Importing this package does not import Textual; only `app` does.
"""

TEXTUAL_HINT = ("ESSENCE needs Textual, from the essence extra: "
                "pip install 'sol-organizes-logic[essence]' (or: pipx inject sol-organizes-logic textual).")


def textual_available():
    from importlib.util import find_spec
    return find_spec("textual") is not None
