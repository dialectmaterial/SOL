"""Small bundled reading list; loading it needs no corpus, UI or network."""
from importlib.resources import files
import json


def load_catalog():
    """Read the bundled data afresh, independently of the working directory."""
    return json.loads(files("sol.essence").joinpath("encyclopedia.json").read_text(encoding="utf-8"))


def entry_markdown(catalog, entry):
    """Keep the verbatim excerpt, attribution and SOL's own note distinct."""
    # Editorial omission marker belongs to presentation, never the stored quote.
    leading = '… ' if entry.get('quote_starts_mid_sentence', False) else ''
    history = entry['article_url'] + '?action=history'
    further = '\n'.join(f"- [{link['title']}]({link['url']})" for link in entry['further'])
    return (f"## {entry['title']}\n\n"
            f"Wikipedia verbatim excerpt:\n\n> {leading}{entry['quote']}\n\n"
            f"— {catalog['attribution']}, *{entry['article_title']}* "
            f"([contributors and history]({history})). "
            f"[{catalog['license']}]({catalog['license_url']}); excerpt unchanged.\n\n"
            f"Article: [{entry['article_url']}]({entry['article_url']})  \n"
            f"Accessed: {catalog['accessed']}\n\n"
            f"### In ESSENCE\n\n{entry['essence']}\n\n"
            f"### Further reading\n\n{further}\n")
