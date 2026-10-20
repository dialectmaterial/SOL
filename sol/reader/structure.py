"""Human-facing book hierarchy; paths are display keys, not object identities."""
from sol.core.models import node_path
from sol.core.paths import display_path


def structure_payload(book, current):
    first = {}
    for passage in book.passages:
        for depth in range(len(passage.path) + 1):
            first.setdefault(passage.path[:depth], passage.identifier)
    nodes, seen = [], set()
    def visit(node, parent=None):
        path = node_path(node)
        key = display_path(path)
        if key in seen:
            raise ValueError("book hierarchy contains a repeated structural path")
        seen.add(key)
        nodes.append({"key": key, "parent": parent, "title": node.title,
                      "children": [display_path(node_path(child)) for child in node.children],
                      "target": first.get(path),
                      "page": None if node.start_page is None else str(node.start_page)})
        for child in node.children:
            visit(child, key)
    visit(book.root)
    return {"nodes": nodes, "current": display_path(current.path),
            "doctrine": display_path(current.path[:1]), "depth": 2}
