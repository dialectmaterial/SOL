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


def genealogy_rows(catalog):
    """The genealogy as drawn lines: a year column, then a tree of descent.

    Each row is a dict with the year, the tree prefix, the label and detail,
    the encyclopedia entry it opens (None for an ancestor without an entry)
    and whether ESSENCE runs that method. Children follow their parent in the
    order the catalog lists them.
    """
    nodes = catalog["genealogy"]["nodes"]
    entries = {entry["id"]: entry for entry in catalog["entries"]}
    children = {}
    for node in nodes:
        children.setdefault(node["parent"], []).append(node)
    rows = []

    def visit(node, prefix, last, depth):
        branch = "" if depth == 0 else prefix + ("└─ " if last else "├─ ")
        entry = entries.get(node["entry"]) if node["entry"] else None
        rows.append({"year": node["year"], "prefix": branch, "label": node["label"], "detail": node["detail"],
                     "entry": node["entry"], "source": node["source"],
                     "runs": bool(entry and entry["essence"].startswith("Runs in ESSENCE"))})
        below = children.get(node["id"], [])
        for index, child in enumerate(below):
            visit(child, "" if depth == 0 else prefix + ("   " if last else "│  "), index == len(below) - 1, depth + 1)

    for root in children.get(None, []):
        visit(root, "", True, 0)
    return rows
