"""Shared, interface-independent operations for SOL components.

BEING and future ESSENCE applications use the same verified corpus and permanent
identifiers. Importing this API never starts a shell, opens a workspace, extracts
a PDF, or loads an optional interface. This is an internal library boundary;
independently distributed components are a subsequent packaging step.
"""

from importlib import import_module

# Python API compatibility is distinct from corpus and workspace schema versions.
API_VERSION = 1

_EXPORTS = {
    "Book": "sol.core.models",
    "Node": "sol.core.models",
    "Passage": "sol.core.models",
    "node_path": "sol.core.models",
    "presentation_text": "sol.core.models",
    "Reference": "sol.core.references",
    "resolve_reference": "sol.core.references",
    "resolve_record_reference": "sol.core.references",
    "PROTOCOL_VERSION": "sol.core.protocol",
    "MAX_REFERENCE_BYTES": "sol.core.protocol",
    "ProtocolError": "sol.core.protocol",
    "capture_reference": "sol.core.protocol",
    "check_reference": "sol.core.protocol",
    "encode_reference": "sol.core.protocol",
    "decode_reference": "sol.core.protocol",
    "alias": "sol.core.paths",
    "child_by_name": "sol.core.paths",
    "display_path": "sol.core.paths",
    "resolve_path": "sol.core.paths",
    "load_corpus_book": "sol.core.corpus",
    "CorpusError": "sol.corpus.contract",
    "CorpusSnapshot": "sol.corpus.contract",
    "load_snapshot": "sol.corpus.contract",
    "verify_snapshot_current": "sol.corpus.contract",
    "discover_corpus": "sol.core.config",
    "save_corpus": "sol.core.config",
}

__all__ = ["API_VERSION", *_EXPORTS]


def __getattr__(name: str):
    """Load only the requested API area, with identity-preserving exports."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
