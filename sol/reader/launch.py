"""Interactive actor/workspace selection, separate from command dispatch."""
from __future__ import annotations

from pathlib import Path
import sys

from sol.core.models import Book


def interactive_input_available() -> bool:
    return bool(sys.stdin.isatty())


def _end_placeholder() -> None:
    # Questions need the plain terminal: close the reader's start-up placeholder.
    module = sys.modules.get("sol.terminal.neovim_reader")
    if module is not None:
        module.end_placeholder()


def shell_identity(book: Book, args) -> None:
    """Resolve explicit launch choices, then ask only when no remembered choice exists.

    The actor registry is not a recency service. Workspace activity dates may
    order a chooser, but never identify the next author or silently select a
    workspace. Only a previously validated interactive launch supplies defaults.
    """
    from sol.workspace.launch import read_launch_preferences
    from sol.workspace.profiles import actor_name, list_actors
    from sol.workspace.reader import workspace_path
    from sol.workspace.store import Workspace

    if not book.corpus_manifest.get('corpus_id'):
        raise ValueError("a persistent reader needs an identified Markdown corpus. "
                         "Run sol-corpus-check DIRECTORY --initialize-identity, or use sol -n.")
    known = list_actors()
    preferences = read_launch_preferences()
    registered_names = {profile['name'] for profile in known}
    if args.actor is None and preferences['last_actor'] in registered_names:
        args.actor = preferences['last_actor']
    if args.actor is None:
        if not interactive_input_available():
            raise ValueError("actor setup needs interactive input. Supply --actor NAME --workspace NAME, "
                             "use sol -n for a temporary reader, or sol -r for a random passage.")
        _end_placeholder()
        if known:
            print('Known actors: ' + ', '.join(profile['name'] for profile in known[-10:]))
        while True:
            value = input('Actor (name for your own notes): ')
            try:
                args.actor = actor_name(value)
            except ValueError as error:
                print(f'sol: {error}')
                continue
            break
    else:
        args.actor = actor_name(args.actor)
    if args.workspace is not None:
        return
    source_digest = book.corpus_manifest.get('source', {}).get('sha256')
    for choice in preferences['selections']:
        if (choice['actor'] != args.actor or choice['corpus_id'] != book.corpus_manifest['corpus_id'] or
                choice['source_sha256'] != source_digest):
            continue
        location = Path(choice['workspace'])
        if args.workspace_dir is not None and workspace_path(location.stem, args.workspace_dir) != location:
            continue
        if location.is_file() and not location.is_symlink():
            # Validate the remembered file read-only before adopting it. Never
            # recreate an absent remembered workspace without asking.
            with Workspace(location, book.corpus_manifest['corpus_id'],
                           {'source_sha256': source_digest}, read_only=True):
                pass
            args.workspace, args.workspace_dir = location.stem, location.parent
            return
    if not interactive_input_available():
        raise ValueError("workspace setup needs interactive input. Supply --workspace NAME --actor NAME, "
                         "use sol -n for a temporary reader, or sol -r for a random passage.")
    _end_placeholder()
    from sol.workspace.catalog import discover_workspaces
    recent = discover_workspaces(book.corpus_manifest['corpus_id'], source_digest, args.workspace_dir)
    if recent:
        print('Available workspaces for this corpus (not actor identities):')
        for number, entry in enumerate(recent, 1):
            print(f"  {number}. {entry['name']} | {entry['last_activity'][:10]} | {entry['scope'] or '[no reading yet]'}")
        print('Choose a displayed number or workspace name; enter a new name to create one.')
    while True:
        prompt = (f'Workspace for {args.actor} [reading]: ' if recent else
                  f'Create workspace for {args.actor} [reading]: ')
        response = input(prompt).strip()
        name = response or 'reading'
        if recent and response.isdecimal():
            number = int(response) if len(response) <= 2 else 0
            if not 1 <= number <= len(recent):
                print('sol: choose a displayed workspace number or a name (use --workspace for a numeric name)')
                continue
            name = recent[number - 1]['name']
        try:
            workspace_path(name, args.workspace_dir)
        except ValueError as error:
            print(f'sol: {error}')
            continue
        args.workspace = name
        return
