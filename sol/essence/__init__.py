"""Small, reproducible experiments over SOL's verified canonical corpus.

ESSENCE consumes CORE data; importing it never starts a reader or native shell.
"""

from importlib import import_module

__all__ = ["MAX_RESULT_BYTES", "TermExperimentError", "analyze_term", "check_term_result",
           "encode_term_result", "decode_term_result"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("sol.essence.terms"), name)
    globals()[name] = value
    return value
