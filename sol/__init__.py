"""SOL Organizes Logic: a philosophical reading workspace."""

__version__ = "0.1.0"


def cli() -> int:
    """Launch the reader without loading optional integrations on import."""
    from .app.main import cli as reader_cli

    return reader_cli()
