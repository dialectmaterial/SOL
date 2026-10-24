"""Bundled presentation vocabulary; never an analysis-input filter."""
from importlib.resources import files
import json


def load_function_words() -> dict:
    """Return fresh metadata/categories and their immutable token union.

    The caller chooses whether to hide matching display rows (default off).
    Membership says nothing about a token's grammatical role in context.
    """
    catalog = json.loads(files("sol.essence").joinpath("function_words.json").read_text(encoding="utf-8"))
    catalog["words"] = frozenset(word for words in catalog["categories"].values() for word in words)
    return catalog
