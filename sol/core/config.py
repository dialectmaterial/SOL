"""Portable local corpus selection, independent of readers and integrations."""

from __future__ import annotations

from importlib import metadata as package_metadata
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit


def config_path() -> Path:
    """Keep the corpus pointer outside the package, following the XDG layout."""
    configured = os.environ.get("XDG_CONFIG_HOME")
    directory = Path(configured).expanduser() if configured else Path.home() / ".config"
    if not directory.is_absolute():
        raise ValueError("XDG_CONFIG_HOME must be an absolute directory")
    return directory / "sol" / "config.json"


def _read_config(reset: str) -> dict | None:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeError) as error:
        raise ValueError(f"Cannot read SOL configuration {path}: {error}\n"
                         f"Reset it with {reset}.") from error
    return data if isinstance(data, dict) else {}


def _write_config(**values) -> Path:
    """Atomically replace the file, keeping settings another command saved."""
    path = config_path()
    try:
        current = _read_config("a new sol --set-corpus or --set-theme") or {}
    except ValueError:
        current = {}
    current.update(values, version=1)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".config-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(current, stream, indent=2)
            stream.write("\n")
        temporary.replace(path)
    except OSError as error:
        raise ValueError(f"Cannot save SOL configuration {path}: {error}") from error
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path


def configured_corpus() -> Path | None:
    path = config_path()
    data = _read_config("sol --set-corpus DIRECTORY")
    if data is None or ("corpus" not in data and "theme" in data):
        return None
    value = data.get("corpus")
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ValueError(f"Invalid SOL configuration {path}: corpus must be an absolute path.\n"
                         "Reset it with sol --set-corpus DIRECTORY.")
    return Path(value)


def installed_project_directory() -> Path | None:
    """Recover a local pip/pipx checkout, without putting its corpus in a wheel.

    PEP 610 records a local-directory install's file URL in direct_url.json.
    Archive and remote Git installations do not identify a persistent checkout.
    """
    try:
        origin = package_metadata.distribution("sol-organizes-logic").read_text("direct_url.json")
        if not origin:
            return None
        data = json.loads(origin)
        if not isinstance(data, dict) or not isinstance(data.get("dir_info"), dict):
            return None
        if "archive_info" in data or "vcs_info" in data:
            return None
        url = data.get("url")
        if not isinstance(url, str):
            return None
        parsed = urlsplit(url)
        if (parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}
                or parsed.query or parsed.fragment):
            return None
        decoded = unquote(parsed.path, errors="strict")
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", decoded):
            decoded = decoded[1:]
        directory = Path(decoded)
        if not directory.is_absolute():
            return None
        subdirectory = data.get("subdirectory", "")
        if not isinstance(subdirectory, str):
            return None
        relative = Path(subdirectory)
        if relative.is_absolute() or ".." in relative.parts:
            return None
        return directory / relative
    except (package_metadata.PackageNotFoundError, OSError, ValueError, TypeError):
        return None


def source_project_directory() -> Path | None:
    """Recognize this source checkout, never guess a corpus beside a module.

    The fallback is for running ``python -m sol`` directly. Installed wheels
    normally have no project metadata; local pipx installs use PEP 610 instead.
    Match the known project's identity within its project table, without adding
    a TOML parser dependency to the Python 3.10 standard-library reader.
    """
    module = Path(__file__).resolve()
    try:
        directory = module.parents[2]
        if module != directory / "sol" / "core" / "config.py":
            return None
        metadata = (directory / "pyproject.toml").read_text(encoding="utf-8")
    except (IndexError, OSError, UnicodeError):
        return None
    project = re.search(r"(?ms)^[ \t]*\[project\][ \t]*(?:#[^\n]*)?\r?\n(.*?)(?=^[ \t]*\[|\Z)", metadata)
    if project is None:
        return None
    identity = re.search(
        r"(?m)^[ \t]*name[ \t]*=[ \t]*(['\"])sol-organizes-logic\1[ \t]*(?:#[^\n]*)?\r?$",
        project.group(1),
    )
    return directory if identity is not None else None


def discover_corpus(explicit: Path | None = None) -> Path | None:
    """Select a canonical corpus independently of the shell's working directory.

    An explicitly selected or saved location must never silently change sources
    when broken. Auto-discovered locations are used only when a manifest exists.
    """
    if explicit is not None:
        return explicit.expanduser()
    environment = os.environ.get("SOL_CORPUS")
    if environment:
        return Path(environment).expanduser()
    local = Path.cwd() / "local-corpus"
    if (local / "corpus.json").is_file():
        return local
    saved = configured_corpus()
    if saved is not None:
        return saved
    project = installed_project_directory()
    candidates = ([project / "local-corpus"] if project is not None else [])
    source = source_project_directory()
    if source is not None:
        candidates.append(source / "local-corpus")
    return next((candidate for candidate in candidates if (candidate / "corpus.json").is_file()), None)


def save_corpus(directory: Path) -> tuple[Path, Path]:
    """Validate first, then atomically save a portable absolute corpus pointer."""
    from sol.core.corpus import load_corpus_book

    corpus = directory.expanduser().resolve()
    if corpus.suffix.lower() == ".pdf" and not corpus.is_dir():
        from shlex import quote
        raise ValueError(
            "--set-corpus expects an indexed corpus directory containing corpus.json, not a PDF.\n"
            "For the supported source PDF, first create a local corpus:\n"
            f"  sol-corpus convert --pdf {quote(str(corpus))} --output local-corpus\n"
            "Then select the resulting directory: sol --set-corpus local-corpus"
        )
    load_corpus_book(corpus)
    return corpus, _write_config(corpus=str(corpus))


def configured_theme(choices, renamed=None) -> str | None:
    """The reader preset saved by sol --set-theme; the reader supplies the names.

    `renamed` maps names saved by earlier versions to their current preset.
    """
    data = _read_config("sol --set-theme NAME")
    value = None if data is None else data.get("theme")
    value = (renamed or {}).get(value, value)
    if value is not None and value not in choices:
        raise ValueError(f"Invalid SOL configuration {config_path()}: theme must be one of "
                         f"{', '.join(choices)}.\nReset it with sol --set-theme NAME.")
    return value


def save_theme(name: str, choices) -> Path:
    if name not in choices:
        raise ValueError(f"reader theme must be one of: {', '.join(choices)}")
    return _write_config(theme=name)
