"""The Encyclopedia and Methods catalogs, as reference opened over a study.

ESSENCE opens on its study; the catalogs are what one consults about it:
`K` opens the current study's method, `M` the catalogs, `:` any entry.
Dismissing with "Use this method" hands the method's study back to the app.
"""
from __future__ import annotations

import unicodedata

from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Markdown, OptionList, Static, TabbedContent, TabPane
from textual.widgets.option_list import Option

from sol.essence.encyclopedia import entry_markdown, genealogy_rows
from sol.essence.methods import method_markdown
from sol.essence.tui.results import focus_now

# Screens that browse a bundled catalog, with their one-line help.
BROWSERS = {
    "encyclopedia": "Encyclopedia · ↑↓ browse · Enter read / explore map · Esc contents",
    "methods": "Methods · ↑↓ browse · Enter read · Esc methods",
}
METHOD_STUDIES = {"words": "words", "word-comparison": "words", "tfidf": "tfidf", "sentences": "sentences"}


def normalized_query(value):
    return unicodedata.normalize("NFC", value.strip()).casefold().replace("’", "'")


class ReferenceScreen(Screen):
    """Both catalogs in two tabs; Escape on a list goes back to the study."""

    BINDINGS = [
        Binding("1", "tab('encyclopedia')", "Encyclopedia", show=False),
        Binding("2", "tab('methods')", "Methods", show=False),
        Binding("escape", "back", "Back to the study"),
    ]

    def __init__(self, tab="encyclopedia", method=None):
        super().__init__()
        self.pending = (tab, method)

    def open(self, tab="encyclopedia", method=None):
        """What to show at the next opening; searches and selections stay as they were."""
        self.pending = (tab, method)
        if self.is_mounted:
            self.apply_pending()

    @property
    def catalog(self):
        return self.app.catalog

    @property
    def methods(self):
        return self.app.methods

    def compose(self):
        yield Static("", id="reference-header")
        with TabbedContent(id="catalogs"):
            for number, (name, label) in enumerate((("encyclopedia", "Encyclopedia"), ("methods", "Methods")), 1):
                with TabPane(f"{number} {label}", id=name):
                    yield from self.compose_browser(name)
        yield Footer(compact=True)

    def compose_browser(self, name):
        with Horizontal(classes="browser-tools"):
            yield Input(placeholder="/ Find a topic" if name == "encyclopedia" else "/ Find a method",
                        id=f"{name}-search", classes="browser-search")
            yield Static("", id=f"{name}-count", classes="browser-count", markup=False)
        with Horizontal(classes="browser-layout"):
            yield OptionList(*self.browser_options(name), id=f"{name}-list", classes="browser-list")
            with VerticalScroll(id=f"{name}-detail", classes="browser-detail"):
                yield Markdown(self.browser_markdown(name, 0), id=f"{name}-entry")
                if name == "encyclopedia":
                    yield OptionList(*self.genealogy_options(), id="genealogy-map")
                    yield Markdown(self.genealogy_sources(), id="genealogy-sources")
        if name == "methods":
            with Horizontal(id="method-actions"):
                yield Button("Use this method", id="use-method")
                yield Static("Choose its sources in the study menu", id="method-availability")

    def on_mount(self):
        self.update_header()
        for name, title in {"encyclopedia-list": "Contents", "encyclopedia-detail": "Encyclopedia",
                            "methods-list": "Available methods", "methods-detail": "Method"}.items():
            self.query_one(f"#{name}").border_title = title
        for name in BROWSERS:
            self.query_one(f"#{name}-search").tooltip = "Find by title, identifier or description. " + BROWSERS[name]
            self.query_one(f"#{name}-list").border_subtitle = "/ Find · Enter read"
            self.query_one(f"#{name}-detail").border_subtitle = "Esc contents"
            self.update_browser(name)
        self.apply_pending()

    def update_header(self):
        self.query_one("#reference-header", Static).update(Text.assemble(
            ("ESSENCE", self.app.title_style()), ("  reference", "bold"),
            ("  ·  1 Encyclopedia · 2 Methods · / find · Esc back to the study", "dim")))

    def apply_pending(self):
        tab, method = self.pending
        if method is not None:
            ids = [item["id"] for item in self.methods["entries"]]
            if method in ids:
                # The method may be outside the current search; reveal it first.
                field = self.query_one("#methods-search", Input)
                if field.value:
                    with self.prevent(Input.Changed):
                        field.value = ""
                    self.filter_browser("methods")
                self.query_one("#methods-list", OptionList).highlighted = ids.index(method)
                self.update_browser("methods")
        self.action_tab(tab)

    def action_tab(self, name):
        self.set_focus(None)
        self.query_one("#catalogs", TabbedContent).active = name
        focus_now(self.query_one(f"#{name}-list"))

    def action_back(self):
        self.dismiss(None)

    # Catalog browsing (unchanged from the former Encyclopedia and Methods screens)
    def browser_items(self, name):
        return (self.catalog if name == "encyclopedia" else self.methods)["entries"]

    def browser_markdown(self, name, index):
        if name == "encyclopedia":
            if index == 0:
                return self.genealogy_markdown()
            return entry_markdown(self.catalog, self.browser_items(name)[index - 1])
        item = self.browser_items(name)[index]
        titles = {entry["id"]: entry["title"] for entry in self.catalog["entries"]}
        reference = item["encyclopedia"]
        return method_markdown(dict(item, encyclopedia=None if reference is None else
                                    f"*{titles.get(reference, reference)}*, under Encyclopedia (1)."))

    def browser_options(self, name, query=""):
        """Stable option IDs keep filtered positions separate from catalog entries."""
        entries = ([{"title": "Genealogy", "essence": self.catalog["genealogy"]["note"]}]
                   if name == "encyclopedia" else []) + self.browser_items(name)
        query = normalized_query(query)
        return [Option(Text(item["title"]), id=str(index)) for index, item in enumerate(entries)
                if query in normalized_query(" ".join((item["title"], item.get("id", ""),
                                                       item.get("essence", item.get("summary", "")))))]

    def browser_index(self, name):
        option = self.query_one(f"#{name}-list", OptionList).highlighted_option
        return int(option.id) if option is not None else None

    def filter_browser(self, name):
        listing = self.query_one(f"#{name}-list", OptionList)
        selected = self.browser_index(name)
        field = self.query_one(f"#{name}-search", Input)
        options = self.browser_options(name, field.value)
        ids = [option.id for option in options]
        with self.prevent(OptionList.OptionHighlighted):
            listing.set_options(options)
            listing.highlighted = ids.index(str(selected)) if str(selected) in ids else 0 if ids else None
        self.update_browser(name)

    def update_browser(self, name):
        index = self.browser_index(name)
        total = len(self.browser_items(name)) + (name == "encyclopedia")
        shown = self.query_one(f"#{name}-list", OptionList).option_count
        self.query_one(f"#{name}-count", Static).update(f"{shown} / {total}")
        detail = self.query_one(f"#{name}-detail", VerticalScroll)
        if index is None:
            content = "## No matches\n\nTry a shorter search, or press Escape in the search field to show all entries."
        else:
            content = self.browser_markdown(name, index)
        detail.border_title = "Encyclopedia" if name == "encyclopedia" else "Method"
        self.query_one(f"#{name}-entry", Markdown).update(content)
        detail.scroll_home(animate=False)
        if name == "methods":
            self.update_method_action(index)
        else:
            for part in ("#genealogy-map", "#genealogy-sources"):
                self.query_one(part).display = index == 0

    def update_method_action(self, index):
        if index is None:
            self.query_one("#use-method", Button).disabled = True
            self.query_one("#method-availability", Static).update("Find a method to configure it")
            return
        item = self.methods["entries"][index]
        supported = item["id"] in METHOD_STUDIES
        self.query_one("#use-method", Button).disabled = not supported
        self.query_one("#method-availability", Static).update(
            "Choose its sources in the study menu" if supported else "CLI operation · command shown above")

    def genealogy_options(self):
        """One line per method: year, line of descent, ● runs in ESSENCE, ○ a reading topic."""
        options = []
        for row in genealogy_rows(self.catalog):
            mark = "● " if row["runs"] else "○ " if row["entry"] else ""
            line = Text.assemble((f"{row['year']:>5}  ", "dim"), (row["prefix"], "dim"), (mark, "bold"),
                                 (row["label"], "" if row["entry"] else "italic"),
                                 ((" · " + row["detail"]) if row["detail"] else "", "dim"))
            options.append(Option(line, disabled=row["entry"] is None))
        return options

    def genealogy_markdown(self):
        genealogy = self.catalog["genealogy"]
        return (f"## {genealogy['title']}\n\n{genealogy['note']}\n\n"
                "● ESSENCE runs it · ○ a reading topic. Arrows move through the map; Enter opens a method.\n")

    def genealogy_sources(self):
        sources = ", ".join(f"[{row['label']}]({row['source']})" for row in genealogy_rows(self.catalog)
                            if row["source"])
        return f"Dates from Wikipedia, accessed {self.catalog['genealogy']['accessed']}: {sources}."

    def on_option_list_option_highlighted(self, event):
        name = (event.option_list.id or "").removesuffix("-list")
        if name in BROWSERS:
            # Ignore highlight messages queued before a newer search rebuilt the list.
            if event.option_id == str(self.browser_index(name)):
                self.update_browser(name)

    def on_option_list_option_selected(self, event):
        if event.option_list.id == "genealogy-map":
            # A method on the map opens its entry, as if chosen from the list.
            entry = genealogy_rows(self.catalog)[event.option_index]["entry"]
            ids = [item["id"] for item in self.catalog["entries"]]
            if entry in ids:
                # A map entry may be outside the current search; reveal it first.
                with self.prevent(Input.Changed):
                    self.query_one("#encyclopedia-search", Input).value = ""
                self.filter_browser("encyclopedia")
                self.query_one("#encyclopedia-list", OptionList).highlighted = ids.index(entry) + 1
                self.update_browser("encyclopedia")
                focus_now(self.query_one("#encyclopedia-detail"))
            return
        name = (event.option_list.id or "").removesuffix("-list")
        if name not in BROWSERS or event.option_id != str(self.browser_index(name)):
            return
        if name == "encyclopedia" and self.browser_index(name) == 0:
            focus_now(self.query_one("#genealogy-map", OptionList))
        else:
            focus_now(self.query_one(f"#{name}-detail"))

    def on_input_changed(self, event):
        name = (event.input.id or "").removesuffix("-search")
        if name in BROWSERS and event.value == event.input.value:
            self.filter_browser(name)

    def on_input_submitted(self, event):
        name = (event.input.id or "").removesuffix("-search")
        if name in BROWSERS and self.browser_index(name) is not None:
            focus_now(self.query_one(f"#{name}-list"))

    def on_button_pressed(self, event):
        if event.button.id == "use-method":
            index = self.browser_index("methods")
            if index is not None and self.methods["entries"][index]["id"] in METHOD_STUDIES:
                self.dismiss(self.methods["entries"][index]["id"])

    def on_key(self, event):
        active = self.query_one("#catalogs", TabbedContent).active
        if active not in BROWSERS:
            return
        field = self.query_one(f"#{active}-search", Input)
        listing = self.query_one(f"#{active}-list")
        if self.focused is field:
            if event.key == "escape":
                if field.value:
                    field.value = ""
                else:
                    focus_now(listing)
                event.stop()
                event.prevent_default()
            return
        if event.key in ("slash", "/", "ctrl+f"):
            focus_now(field)
            event.stop()
            event.prevent_default()
        elif event.key == "escape" and self.focused is not listing:
            # From an entry or the map, Escape returns to the list first.
            focus_now(listing)
            event.stop()
            event.prevent_default()
