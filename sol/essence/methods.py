"""Bundled descriptions of runnable ESSENCE methods; no corpus or UI needed."""
from importlib.resources import files
import json


def load_methods():
    """Read a fresh catalog with an entries list, independent of the cwd."""
    return json.loads(files("sol.essence").joinpath("methods.json").read_text(encoding="utf-8"))


def method_markdown(method):
    """Render all method details without changing the catalog entry."""
    inputs = '\n'.join(f"- {item}" for item in method['inputs'])
    settings = '\n'.join(f"- **{item['name']}**: {item['meaning']}" for item in method['settings'])
    limits = '\n'.join(f"- {item}" for item in method['limits'])
    encyclopedia = (f"\n### Encyclopedia\n\n{method['encyclopedia']}\n"
                    if method['encyclopedia'] is not None else '')
    return (f"## {method['title']}\n\n{method['summary']}\n\n"
            f"### Inputs\n\n{inputs}\n\n"
            f"### Settings\n\n{settings}\n\n"
            f"### Output\n\n{method['output']}\n\n"
            f"### Limits\n\n{limits}\n\n"
            f"### CLI\n\n```sh\n{method['cli']}\n```\n"
            f"{encyclopedia}")
