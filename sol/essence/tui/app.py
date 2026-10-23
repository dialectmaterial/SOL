"""ESSENCE interface: four logical screens and reproducible lexical studies.

Neovim owns the outer layout (beside the reader or fullscreen, Alt-F, and
Alt-R back to the reader); this app owns only what is inside its window.
Leaving saves which screen was open and for which passage, nothing else.
"""
from __future__ import annotations

import base64
import json
import unicodedata

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.theme import Theme
from textual import work
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets.option_list import Option
from textual.widgets import (Button, DataTable, Footer, Input, Label, Markdown, OptionList, RadioButton, RadioSet, Static,
                             TabbedContent, TabPane)

from sol.essence.encyclopedia import entry_markdown, genealogy_rows, load_catalog
from sol.essence.methods import load_methods, method_markdown
from sol.essence.tui import sentences, tfidf, words
from sol.essence.tui.context import load_state, save_state
from sol.presentation.theme import DEFAULT_READER_THEME

TEXTUAL_THEMES = {"mocha": "catppuccin-mocha", "latte": "catppuccin-latte", "paper": "sol-paper",
                  "night": "sol-night", "terminal": "ansi-dark"}
# SOL's own, matching the reader's Paper and Night (actualspirit.com).
SOL_THEMES = (
    Theme(name="sol-paper", primary="#55308a", secondary="#45424d", accent="#55308a", warning="#9b2c2c",
          error="#9b2c2c", success="#3d6b3a", foreground="#17151c", background="#f3f0e6", surface="#ebe7d9",
          panel="#e4dfcf", dark=False),
    Theme(name="sol-night", primary="#c3a6ee", secondary="#a29cae", accent="#c3a6ee", warning="#e8a87c",
          error="#e8a87c", success="#a6c99a", foreground="#ece7da", background="#1b1820", surface="#221e28",
          panel="#2a2531", dark=True),
)

SOURCES_HELP = "Occurrences · Enter opens in reader · Escape returns to words"

# Screens that browse a bundled catalog, with their one-line help.
BROWSERS = {
    "encyclopedia": "Encyclopedia · ↑↓ browse · Enter read / explore map · Esc contents",
    "methods": "Methods · ↑↓ browse · Enter read · Esc methods",
}

STUDY_NOTES = {
    "words": "Count words, inspect their occurrences, and compare two sources by normalized rates.\n\n"
             "Counts describe lexical patterns; they do not identify concepts.",
    "sentences": "Explore sentence lengths, their distribution and their position within each passage.\n\n"
                 "Punctuation rules describe the selected translation's sentences.",
    "tfidf": "Rank terms within each passage and across the selected source.\n\n"
             "Weights depend on the chosen documents; they do not establish conceptual significance.",
}

METHOD_STUDIES = {"words": "words", "word-comparison": "words", "tfidf": "tfidf", "sentences": "sentences"}

SCREENS = {
    "encyclopedia": ("Encyclopedia", None),
    "methods": ("Methods", None),
    "experiment": ("Experiment", None),
    "results": ("Results", None),
}


def in_context(context):
    """The words around an occurrence, the word itself in bold."""
    if context is None:
        return Text("(the text has changed since the count)", style="dim")
    # Keep the word's boundary spaces in the same styled segment. This also
    # preserves their placement in SVG screenshots, where separate runs may
    # otherwise collapse or visually shift a space beside the bold glyphs.
    left, word, right = context["left"], context["word"], context["right"]
    if left.endswith(" "):
        left, word = left[:-1], " " + word
    if right.startswith(" "):
        word, right = word + " ", right[1:]
    return Text.assemble(left, (word, "bold"), right)


class WordSort(ModalScreen):
    """A keyboard menu with explicit column and direction choices."""

    BINDINGS = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    WordSort { align: center middle; }
    #sort-dialog { width: 52; max-width: 100%; height: 22; max-height: 90%;
                   background: $background; border: round $accent; padding: 1; }
    #sort-options { height: 1fr; }
    #sort-help { height: auto; }
    """

    def __init__(self, current):
        super().__init__()
        self.current = current
        self.choices = [(None, False), *((column, descending)
                        for column in range(len(words.SORT_COLUMNS)) for descending in (False, True))]

    def compose(self) -> ComposeResult:
        with Vertical(id="sort-dialog"):
            yield Static("Sort words · undefined values always last\n"
                         "Arrows choose · Enter applies · Escape cancels", id="sort-help")
            yield OptionList("Engine order (default)",
                             *(f"{words.SORT_COLUMNS[column]} · {'descending' if descending else 'ascending'}"
                               for column, descending in self.choices[1:]), id="sort-options")

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        options.highlighted = self.choices.index(self.current)
        options.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.choices[event.option_index])

    def action_cancel(self) -> None:
        self.dismiss(None)


class EssenceApp(App):
    """One investigation, shown in whatever space Neovim gives it."""

    TITLE = "SOL ESSENCE"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: $background; }
    #masthead { height: 1; padding: 0 2; }
    #brand { width: 1fr; color: $success; text-style: bold; }
    #masthead-note { width: auto; color: $text-muted; }
    #origin { height: 1; padding: 0 2; color: $text-muted; text-overflow: ellipsis; text-wrap: nowrap; }
    #workspace, #screens, ContentSwitcher { height: 1fr; }
    ContentTabs { background: $background; }
    Tab { color: $text-muted; padding: 0 2; }
    Tab.-active { color: $accent; text-style: bold; }
    TabPane { padding: 0 1; }
    .browser-help { height: 1; color: $text-muted; text-overflow: ellipsis; text-wrap: nowrap; }
    .browser-layout { height: 1fr; }
    .browser-list, .browser-detail, .setup-panel, .choice-group,
    #tfidf-settings, #summary-box, DataTable, #empty-results {
        border: round $primary 45%; background: $background;
        border-title-color: $text-muted; border-title-style: bold;
    }
    .browser-list:focus, .browser-detail:focus, .setup-panel:focus-within,
    .choice-group:focus-within, #tfidf-settings:focus-within, DataTable:focus,
    #summary-box:focus { border: round $accent; border-title-color: $accent; }
    .browser-list { width: 32; height: 1fr; padding: 0 1; margin-right: 1; }
    .browser-detail { width: 1fr; height: 1fr; padding: 0 1; }
    #method-actions { height: 1; margin-top: 1; }
    #method-actions Button { height: 1; border: none; min-width: 20; }
    #method-availability { width: 1fr; color: $text-muted; }
    OptionList { background: $background; }
    OptionList > .option-list--option { padding: 0 1; }
    OptionList > .option-list--option-highlighted { background: $primary 18%; color: $foreground; text-style: bold; }
    OptionList:focus > .option-list--option-highlighted { background: $primary 30%; color: $foreground; }
    Markdown { padding: 0 1; }
    MarkdownH2 { margin-top: 0; }
    #genealogy-map { height: auto; border: none; background: transparent; padding: 0 1; }
    #experiment-layout { height: 1fr; }
    #study-panel { width: 32; height: 1fr; padding: 0 1; margin-right: 1; }
    #study { height: auto; }
    #study-note { height: auto; color: $text-muted; margin-top: 2; padding: 0 1; }
    #experiment-body { width: 1fr; height: 1fr; padding: 0 1; border: round $primary 45%; border-title-color: $text-muted; border-title-style: bold; }
    #experiment-body:focus-within { border: round $accent; border-title-color: $accent; }
    .choices { height: auto; align-vertical: top; }
    .choice-group { height: auto; width: 1fr; padding: 0 1; }
    #reference-group { margin-left: 1; }
    RadioSet { border: none; padding: 0; background: transparent; height: auto; }
    RadioButton { border: none; padding: 0 1; background: transparent; }
    RadioButton:focus { text-style: bold; }
    RadioButton > .toggle--button { background: transparent; color: $text-muted; }
    RadioButton.-on > .toggle--button { color: $accent; }
    Input { margin: 0; border: round $primary 45%; background: $surface; }
    Input:focus { border: round $accent; }
    #tfidf-settings { height: auto; padding: 0 1; margin-top: 1; }
    #tfidf-settings Label { height: auto; color: $text-muted; }
    #run-row { height: 3; margin-top: 1; }
    Button { min-width: 12; height: 3; margin-right: 1; border: round $primary 45%; background: $surface; }
    #run, #configure { background: $primary; color: $text; text-style: bold; border: round $primary; }
    #run:focus, #configure:focus { border: round $accent; text-style: bold reverse; }
    #cancel { background: $background; }
    #status { height: auto; color: $text-muted; }
    #results, #results-workspace { height: 1fr; }
    #results-workspace { display: none; }
    #empty-results { height: 1fr; align: center middle; padding: 1 3; }
    #empty-results Static { height: auto; width: 100%; text-align: center; color: $text-muted; margin-bottom: 1; }
    #summary { padding: 0; }
    #result-toolbar { height: auto; min-height: 1; max-height: 2; }
    #result-metrics { height: auto; width: 1fr; }
    #toggle-details { height: 1; min-width: 13; margin: 0; border: none; background: $surface; }
    #summary-box { display: none; height: 30%; min-height: 3; max-height: 10; padding: 0 1; }
    #word-tools { height: 1; margin-top: 1; }
    #word-filter { height: 1; width: 1fr; border: none; background: $surface; padding: 0 1; }
    #word-filter:focus { background: $primary 18%; }
    #sort-words { height: 1; min-width: 10; margin: 0 0 0 1; border: none; }
    #sort-status { height: 1; color: $text-muted; text-overflow: ellipsis; text-wrap: nowrap; }
    #frequencies { height: 1fr; min-height: 4; }
    DataTable > .datatable--header { background: $surface; color: $text-muted; text-style: bold; }
    DataTable > .datatable--cursor { background: $primary 25%; color: $foreground; }
    DataTable:focus > .datatable--cursor { background: $primary 40%; color: $foreground; text-style: bold; }
    #sources-label, #overall-label { color: $text-muted; height: 1; text-overflow: ellipsis; text-wrap: nowrap; }
    #sources { height: 1fr; min-height: 4; }
    #overall { height: 1fr; min-height: 4; max-height: 30%; }
    #export-row { height: 1; }
    #export-row Button { height: 1; border: none; background: $surface; }
    #result-status { color: $text-muted; height: auto; }
    #layout-hint { height: 1; padding: 0 2; color: $text-muted; text-overflow: ellipsis; text-wrap: nowrap; }
    Footer { background: $surface; }
    Screen.-compact .browser-layout { layout: vertical; }
    Screen.-compact .browser-list { width: 1fr; height: 8; min-height: 4; max-height: 35%; margin: 0 0 1 0; }
    Screen.-compact .browser-detail { width: 1fr; }
    Screen.-compact #experiment-layout { layout: vertical; }
    Screen.-compact #study-panel { width: 1fr; height: auto; margin: 0 0 1 0; }
    Screen.-compact #study-note { display: none; }
    Screen.-compact #experiment-body { width: 1fr; }
    Screen.-compact Tab { padding: 0 1; }
    Screen.-compact #masthead-note { display: none; }
    Screen.-compact #word-tools { margin-top: 0; }
    Screen.-compact #summary-box { height: 3; max-height: 3; }
    Screen.-small .choices { layout: vertical; }
    Screen.-small .choice-group { width: 1fr; }
    Screen.-small #reference-group { margin: 1 0 0 0; }
    """
    # The private terminal sequence that asks the reader to open a source; the
    # reader checks it and navigates only through its own guarded actions.
    SOURCE_SEQUENCE = "\x1b]5379;sol-essence;{}\x07"
    BINDINGS = [
        Binding("q", "leave", "Leave ESSENCE"),
        # Priority: the reader sends Ctrl-Q when it quits, whatever has focus.
        Binding("ctrl+q", "leave", "Leave ESSENCE", show=False, priority=True),
        *(Binding(str(number), f"screen('{name}')", label, show=False)
          for number, (name, (label, _)) in enumerate(SCREENS.items(), 1)),
    ]

    def __init__(self, context, theme=DEFAULT_READER_THEME, theme_file=None):
        super().__init__()
        for sol_theme in SOL_THEMES:
            self.register_theme(sol_theme)
        # Textual's own Catppuccin themes; Terminal uses the terminal's ANSI colors.
        self.theme = TEXTUAL_THEMES[theme]
        self.theme_file = theme_file
        self.catalog = load_catalog()
        self.methods = load_methods()
        self.context = context
        self.state_file = context["state_file"]
        self.state = load_state(self.state_file) if self.state_file else {}
        self.word_sort = (None, False)
        self.word_order = []
        self.word_filter = ""
        self.details_caption = "i Details"

    def compose(self) -> ComposeResult:
        target = self.context["reference"]["reference"]["target_id"]
        with Horizontal(id="masthead"):
            yield Static("SOL / ESSENCE", id="brand")
            yield Static("Computational inquiry", id="masthead-note")
        yield Static(f"{self.context['label']} · record {target[:8]}", id="origin", markup=False)
        with Vertical(id="workspace"):
            with TabbedContent(id="screens"):
                for number, (name, (label, text)) in enumerate(SCREENS.items(), 1):
                    with TabPane(f"{number} {label}", id=name):
                        if name in BROWSERS:
                            yield from self.compose_browser(name)
                        elif name == "experiment":
                            yield from self.compose_experiment()
                        elif name == "results":
                            yield from self.compose_results()
                        else:
                            yield Markdown(text)
        yield Static("Alt-F fullscreen ⇄ beside · Alt-R back to the reader · 1–4 screens",
                     id="layout-hint")
        yield Footer()

    # Wide windows browse beside the entry; reader splits stack the same panels.
    def browser_items(self, name):
        return (self.catalog if name == "encyclopedia" else self.methods)["entries"]

    def browser_markdown(self, name, index):
        if name == "encyclopedia":
            if index == 0:
                return self.genealogy_markdown()
            return entry_markdown(self.catalog, self.browser_items(name)[index - 1])
        item = self.browser_items(name)[index]
        # Name the encyclopedia entry, not its ID, and say how to get there.
        titles = {entry["id"]: entry["title"] for entry in self.catalog["entries"]}
        reference = item["encyclopedia"]
        return method_markdown(dict(item, encyclopedia=None if reference is None else
                                    f"*{titles.get(reference, reference)}*, on the Encyclopedia screen (1)."))

    def compose_browser(self, name) -> ComposeResult:
        yield Static(BROWSERS[name], classes="browser-help")
        first = ["Genealogy"] if name == "encyclopedia" else []
        with Horizontal(classes="browser-layout"):
            yield OptionList(*first, *(item["title"] for item in self.browser_items(name)), id=f"{name}-list",
                             classes="browser-list")
            with VerticalScroll(id=f"{name}-detail", classes="browser-detail"):
                yield Markdown(self.browser_markdown(name, 0), id=f"{name}-entry")
                if name == "encyclopedia":
                    yield OptionList(*self.genealogy_options(), id="genealogy-map")
                    yield Markdown(self.genealogy_sources(), id="genealogy-sources")
        if name == "methods":
            with Horizontal(id="method-actions"):
                yield Button("Use this method", id="use-method")
                yield Static("Configure it in Experiment", id="method-availability")

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

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        name = (event.option_list.id or "").removesuffix("-list")
        if name in BROWSERS:
            self.query_one(f"#{name}-entry", Markdown).update(self.browser_markdown(name, event.option_index))
            self.query_one(f"#{name}-detail", VerticalScroll).scroll_home(animate=False)
            if name == "methods":
                self.update_method_action(event.option_index)
            if name == "encyclopedia":
                for part in ("#genealogy-map", "#genealogy-sources"):
                    self.query_one(part).display = event.option_index == 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "genealogy-map":
            # A method on the map opens its entry, as if chosen from the list.
            entry = genealogy_rows(self.catalog)[event.option_index]["entry"]
            ids = [item["id"] for item in self.catalog["entries"]]
            if entry in ids:
                self.query_one("#encyclopedia-list", OptionList).highlighted = ids.index(entry) + 1
                self.query_one("#encyclopedia-detail").focus()
            return
        name = (event.option_list.id or "").removesuffix("-list")
        if name == "encyclopedia" and event.option_index == 0:
            self.query_one("#genealogy-map", OptionList).focus()
        elif name in BROWSERS:
            self.query_one(f"#{name}-detail").focus()

    def compose_experiment(self) -> ComposeResult:
        # Tab goes straight to the choices, not to the scrolling container.
        with Horizontal(id="experiment-layout"):
            with Vertical(id="study-panel", classes="setup-panel"):
                with RadioSet(id="study"):
                    yield RadioButton("Word frequencies", value=True, name="words")
                    yield RadioButton("Sentence lengths", name="sentences")
                    yield RadioButton("TF-IDF · top terms", name="tfidf")
                yield Static(STUDY_NOTES["words"], id="study-note")
            with VerticalScroll(id="experiment-body", can_focus=False):
                with Horizontal(classes="choices"):
                    with Vertical(id="target-panel", classes="choice-group"):
                        with RadioSet(id="target"):
                            for key, label in words.TARGETS.items():
                                yield RadioButton(label, value=key == "passage", name=key)
                        yield Input(placeholder="Target file · UTF-8 path", id="target-file")
                    with Vertical(id="reference-group", classes="choice-group"):
                        with RadioSet(id="reference"):
                            for key, label in words.REFERENCES.items():
                                yield RadioButton(label, value=key == "none", name=key)
                        yield Input(placeholder="Reference file · UTF-8 path", id="reference-file")
                with Vertical(id="tfidf-settings"):
                    yield Label("Terms per passage and overall · 1–1,000")
                    yield Input("20", id="top-n", placeholder="TF-IDF top_n · 1–1,000", type="integer")
                with Horizontal(id="run-row"):
                    yield Button("Run study", id="run")
                    yield Button("Cancel", id="cancel", disabled=True)
                yield Static("", id="status")

    def compose_results(self) -> ComposeResult:
        with Vertical(id="empty-results"):
            yield Static("Your inquiry starts with a question.\n\n"
                         "Choose a study and a source.\nYour measurements and their source passages will appear here.")
            yield Button("Choose a study", id="configure")
        with Vertical(id="results-workspace"):
            with Horizontal(id="result-toolbar"):
                yield Static("", id="result-metrics", markup=False)
                yield Button("i Details", id="toggle-details")
            with VerticalScroll(id="summary-box"):
                yield Static("", id="summary", markup=False)
            with Horizontal(id="word-tools"):
                yield Input(placeholder="/ Filter words · Esc clears", id="word-filter")
                yield Button("s Sort", id="sort-words")
            yield Static("", id="sort-status", markup=False)
            yield DataTable(id="frequencies", zebra_stripes=True, cursor_type="row")
            yield Static("Overall · mean passage weights", id="overall-label")
            yield DataTable(id="overall", cursor_type="row", zebra_stripes=True)
            yield Static(SOURCES_HELP, id="sources-label")
            yield DataTable(id="sources", cursor_type="row")
            with Horizontal(id="export-row"):
                yield Button("Export CSV", id="export-csv", disabled=True)
                yield Button("Export TSV", id="export-tsv", disabled=True)
            yield Static("", id="result-status")

    def choice(self, name: str) -> str:
        pressed = self.query_one(f"#{name}", RadioSet).pressed_button
        return pressed.name if pressed is not None else {"target": "passage", "study": "words"}.get(name, "none")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.update_choices()

    def update_choices(self) -> None:
        comparison = self.choice("study") == "words"
        self.query_one("#study-note", Static).update(STUDY_NOTES[self.choice("study")])
        self.query_one("#reference-group").display = comparison
        self.query_one("#target-file").display = self.choice("target") == "file"
        self.query_one("#reference-file").display = comparison and self.choice("reference") == "file"
        self.query_one("#tfidf-settings").display = self.choice("study") == "tfidf"

    def update_method_action(self, index) -> None:
        item = self.methods["entries"][index]
        supported = item["id"] in METHOD_STUDIES
        self.query_one("#use-method", Button).disabled = not supported
        self.query_one("#method-availability", Static).update(
            "Configure it in Experiment" if supported else "CLI operation · command shown above")
        self.query_one("#methods-detail").border_title = Text(item["title"])

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "word-filter" or not isinstance(self.last_count, words.Count):
            return
        if event.value != event.input.value:
            return  # A new result may already have cleared an old queued edit.
        query = unicodedata.normalize("NFC", event.value.strip()).casefold().replace("’", "'")
        if query != self.word_filter:
            self.word_filter = query
            self.reflow_result()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "word-filter":
            self.query_one("#frequencies").focus()

    def toggle_details(self) -> None:
        box = self.query_one("#summary-box")
        box.display = not box.display
        self.query_one("#toggle-details", Button).label = "i Hide" if box.display else self.details_caption
        (box if box.display else self.query_one("#frequencies")).focus()

    def show_metrics(self, count) -> None:
        if isinstance(count, tfidf.TfidfCount):
            totals = count.study["word_study"]["target"]["summary"]
            notes = count.study["word_study"].get("warnings", [])
            line = f"{totals['token_count']:,} tokens · {totals['input_count']:,} inputs · top {count.study['top_n']} terms"
        elif isinstance(count, sentences.SentenceCount):
            totals = count.study["summary"]
            notes = []
            mean = "—" if totals["mean"] is None else f"{totals['mean']:.1f}"
            line = f"{totals['sentences']:,} sentences · {totals['tokens']:,} words · mean {mean}"
        else:
            totals = count.study["target"]["summary"]
            notes = (count.comparison if count.comparison is not None else count.study).get("warnings", [])
            line = f"Target {totals['token_count']:,} tokens"
            if count.reference is not None:
                line += f" · Reference {count.study['reference']['summary']['token_count']:,} tokens"
            else:
                line += f" · {totals['type_count']:,} distinct words"
        content = Text(line)
        # Include the following space so SVG previews keep the boundary beside
        # bold numbers, just as occurrence contexts keep their word spaces.
        content.highlight_regex(r"\d[\d,]*(?:\.\d+)?(?:\s|$)", "bold")
        self.query_one("#result-metrics", Static).update(content)
        self.query_one("#result-metrics").tooltip = line
        self.details_caption = "i Details" + (f" ({len(notes)})" if notes else "")
        button = self.query_one("#toggle-details", Button)
        button.label = "i Hide" if self.query_one("#summary-box").display else self.details_caption
        button.tooltip = (f"{len(notes)} method/source notes. " if notes else "") + "Study summary, scope, formulas, exclusions and saved-artifact status."

    count_serial = 0
    last_count = None
    shown_sources = ()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "use-method":
            listing = self.query_one("#methods-list", OptionList)
            method = self.methods["entries"][listing.highlighted or 0]["id"]
            study = METHOD_STUDIES.get(method)
            if study is not None:
                for button in self.query("#study RadioButton"):
                    button.value = button.name == study
                if method == "word-comparison" and self.choice("reference") == "none":
                    reference = "book" if self.context["corpus"] else "file"
                    for button in self.query("#reference RadioButton"):
                        button.value = button.name == reference
                self.update_choices()
                self.action_screen("experiment")
        elif event.button.id == "toggle-details":
            self.toggle_details()
        elif event.button.id == "sort-words":
            self.push_screen(WordSort(self.word_sort), self.sort_words)
        elif event.button.id == "configure":
            self.action_screen("experiment")
        elif event.button.id == "run":
            top_n = 20
            if self.choice("study") == "tfidf":
                value = self.query_one("#top-n", Input).value.strip()
                try:
                    top_n = int(value) if value.isascii() and value.isdecimal() else 0
                except ValueError:
                    top_n = 0  # Also refuse values beyond Python's integer-string limit.
                if not 1 <= top_n <= 1000:
                    self.query_one("#status", Static).update("Not counted: top_n must be an integer from 1 to 1,000.")
                    self.query_one("#top-n", Input).focus()
                    return
            # Read the choices here, on the interface thread; each count has a
            # number, and only the latest one may save or show anything.
            self.count_serial += 1
            self.query_one("#status", Static).update("Counting…")
            self.query_one("#cancel", Button).disabled = False
            self.count_words(self.count_serial, self.choice("target"), self.choice("reference"),
                             self.query_one("#target-file", Input).value,
                             self.query_one("#reference-file", Input).value, self.choice("study"), top_n)
        elif event.button.id == "cancel":
            # The engine cannot be interrupted midway: the count finishes in
            # the background, and its result is discarded like a replaced one.
            self.count_serial += 1
            event.button.disabled = True
            self.query_one("#status", Static).update("Cancelled; nothing was saved.")
        elif event.button.id in ("export-csv", "export-tsv") and self.last_count is not None:
            if not self.state_file:
                self.query_one("#result-status", Static).update(
                    "Not exported: this reader session has no workspace, so ESSENCE writes nothing.")
                return
            for button in self.query("#export-row Button"):
                button.disabled = True
            self.query_one("#result-status", Static).update("Checking the sources again and exporting…")
            self.export_table(self.last_count, event.button.id.removeprefix("export-"))

    @work(thread=True, exclusive=True)
    def count_words(self, serial, target, reference, target_file, reference_file, study="words", top_n=20) -> None:
        # The engine reads the corpus or files; keep the interface responsive.
        try:
            if study == "tfidf":
                outcome = tfidf.run(self.context, target, target_file=target_file, top_n=top_n)
            elif study == "sentences":
                outcome = sentences.run(self.context, target, target_file=target_file)
            else:
                outcome = words.run(self.context, target, reference, target_file=target_file,
                                    reference_file=reference_file)
        except (words.EngineMissing, ValueError, OSError) as error:
            outcome = error
        try:
            self.call_from_thread(self.finish_count, serial, outcome)
        except RuntimeError:
            pass  # ESSENCE has closed; nothing is left to update.

    def finish_count(self, serial, outcome) -> None:
        # A replaced or abandoned count saves nothing and shows nothing.
        if serial != self.count_serial:
            return
        self.query_one("#cancel", Button).disabled = True
        status = self.query_one("#status", Static)
        if isinstance(outcome, Exception):
            status.update(f"Not counted: {outcome}")
            return
        try:
            module = (tfidf if isinstance(outcome, tfidf.TfidfCount) else
                      sentences if isinstance(outcome, sentences.SentenceCount) else words)
            saved = module.save(outcome) if self.state_file else None
        except (words.EngineMissing, ValueError, OSError) as error:
            status.update(f"Counted, but not saved: {error}")
            saved = None
        self.show_result(outcome, saved)

    def show_result(self, count, saved) -> None:
        self.query_one("#empty-results").display = False
        self.query_one("#results-workspace").display = True
        if count is not self.last_count:
            self.word_sort = (None, False)
            self.word_filter = ""
            with self.prevent(Input.Changed):
                self.query_one("#word-filter", Input).value = ""
            self.query_one("#summary-box").display = False
            self.query_one("#toggle-details", Button).label = "i Details"
        self.show_metrics(count)
        if isinstance(count, tfidf.TfidfCount):
            return self.show_tfidf(count, saved)
        if isinstance(count, sentences.SentenceCount):
            return self.show_sentences(count, saved)
        self.set_word_widgets(True)
        table = self.query_one("#frequencies", DataTable)
        table.border_title = "Word comparison" if count.reference is not None else "Word frequencies"
        table.clear(columns=True)
        columns = [("Target", 6), ("per 10k", 8)]
        if count.reference is not None:
            columns += [("Reference", 9), ("per 10k", 8)]
        if count.comparison is not None:
            columns += [("Difference", 10), ("Log₂ ratio", 10)]
        budget = self.result_width(len(columns) + 1)
        # Narrow reader splits retain every measurement, folding cells instead
        # of letting fixed numeric widths force the word column off-screen.
        numeric_budget = max(len(columns), budget - min(8, max(4, budget // 5)))
        desired = sum(width for _, width in columns)
        if desired > numeric_budget:
            columns = [(label, max(1, width * numeric_budget // desired)) for label, width in columns]
        table.add_column("Word", width=max(1, budget - sum(width for _, width in columns)))
        for label, width in columns:
            table.add_column(label, width=width)
        ordered = words.row_order(count, *self.word_sort)
        matching = [index for index in ordered if self.word_filter in count.study["frequencies"][index]["word"]]
        self.word_order = matching[:words.ROW_LIMIT]
        shown, total = words.rows(count, order=self.word_order)
        for index, row in zip(self.word_order, shown):
            cells = row if count.reference is not None else row[:3]
            table.add_row(*cells, key=str(index), height=None)
        column, descending = self.word_sort
        sort_status = self.query_one("#sort-status", Static)
        sort_status.display = True
        order_label = "Engine order (default)" if column is None else f"{words.SORT_COLUMNS[column]} · {'descending' if descending else 'ascending'}"
        match_label = (f"{len(shown):,} of {len(matching):,} matching {'word' if len(matching) == 1 else 'words'}" if self.word_filter else
                       f"{len(shown):,} of {total:,} {'word' if total == 1 else 'words'}")
        if self.word_filter and not matching:
            match_label = "No matching words · Esc clears the filter"
        status_label = match_label + (" · " + order_label + " · undefined last" if count.comparison is not None else "")
        sort_status.update(status_label)
        sort_status.tooltip = status_label
        lines = words.summary(count)
        if self.word_filter:
            lines.append(f"Display filter: {self.query_one('#word-filter', Input).value!r}; "
                         f"{len(matching):,} matching words. Counts and exports retain the full study.")
        elif len(shown) < total:
            lines.append(f"Showing the first {len(shown):,} of {total:,} words in the selected order.")
        lines.append(f"Saved: {saved} (check with: sol essence check FILE)" if saved else
                     "Not saved: this reader session has no workspace.")
        self.query_one("#summary", Static).update("\n".join(lines))
        self.query_one("#result-status", Static).update("")
        self.query_one("#status", Static).update(f"Counted {total:,} distinct words; see Results (4).")
        self.last_count = count
        self.last_saved = saved
        for button in self.query("#export-row Button"):
            button.disabled = count.reference is None
        self.query_one("#export-row").display = count.reference is not None
        self.query_one("#sort-words", Button).display = count.comparison is not None
        self.show_sources(self.word_order[0] if self.word_order else None)
        self.query_one("#screens", TabbedContent).active = "results"
        # Words first: arrows choose a word, Enter goes to its sources.
        table.focus()

    def result_width(self, columns):
        """Cell budget: pane padding, scrollbar, then DataTable cell padding.

        Use the viewport, never content widths, so a resize cannot make long
        words, paths or undefined measures force sideways scrolling.
        """
        return max(columns, self.size.width - 6 - 2 * columns)

    def set_word_widgets(self, shown) -> None:
        self.query_one("#sort-status").display = False
        self.query_one("#overall").display = False
        self.query_one("#overall-label").display = False
        self.query_one("#word-tools").display = shown
        # Sources and export belong to word counts only.
        for selector in ("#sources-label", "#sources", "#export-row"):
            self.query_one(selector).display = shown

    def show_sentences(self, count, saved) -> None:
        self.set_word_widgets(False)
        table = self.query_one("#frequencies", DataTable)
        table.border_title = "Longest sentences"
        table.clear(columns=True)
        budget = self.result_width(3)
        length_width = min(7, max(3, budget // 8))
        location_width = min(24, max(8, budget // 3))
        table.add_column("Words", width=length_width)
        table.add_column("Beginning", width=max(1, budget - length_width - location_width))
        table.add_column("Where", width=location_width)
        for row in sentences.rows(count):
            table.add_row(row[0], Text(row[1], overflow="fold"),
                          Text(row[2].replace(" | p. ", "\np. "), overflow="fold"), height=None)
        lines = sentences.summary(count)
        if count.study["longest"]:
            lines.append("The longest sentences are below; Enter opens one in the reader (Alt-Left there returns).")
        lines.append(f"Saved: {saved} (check with: sol essence check FILE)" if saved else
                     "Not saved: this reader session has no workspace.")
        # The length bars take the theme's accent rather than the full ink colour.
        summary = Text("\n".join(lines))
        summary.highlight_regex(r"█+", style=self.current_theme.accent or "bold")
        self.query_one("#summary", Static).update(summary)
        self.query_one("#result-status", Static).update("")
        self.query_one("#status", Static).update(
            f"Measured {count.study['summary']['sentences']:,} sentences; see Results (4).")
        self.last_count = count
        self.last_saved = saved
        self.shown_sources = ()
        self.query_one("#screens", TabbedContent).active = "results"
        table.focus()

    def show_tfidf(self, count, saved) -> None:
        self.set_word_widgets(False)
        table = self.query_one("#frequencies", DataTable)
        table.border_title = "Terms by passage"
        table.clear(columns=True)
        passage_width = min(34, max(20, self.result_width(2) // 3))
        table.add_column("Passage · Enter to open", width=passage_width)
        table.add_column("Top terms · weight", width=self.result_width(2) - passage_width)
        for label, terms in tfidf.rows(count):
            table.add_row(Text(label, overflow="fold"), Text(terms, overflow="fold"), height=None)
        overall = self.query_one("#overall", DataTable)
        overall.clear(columns=True)
        overall.add_column("Term", width=self.result_width(2) - 12)
        overall.add_column("Mean weight", width=12)
        for row in count.study["overall"]:
            overall.add_row(Text(row["word"], overflow="fold"), f"{row['score']:.4f}", height=None)
        overall.display = self.query_one("#overall-label").display = True
        lines = tfidf.summary(count)
        lines.append(f"Saved: {saved}" if saved else "Not saved: this reader session has no workspace.")
        self.query_one("#summary", Static).update("\n".join(lines))
        self.query_one("#result-status", Static).update("")
        self.query_one("#status", Static).update("Ranked top terms; see Results (4).")
        self.last_count = count
        self.last_saved = saved
        self.shown_sources = ()
        self.query_one("#screens", TabbedContent).active = "results"
        table.focus()

    def show_sources(self, index) -> None:
        table = self.query_one("#sources", DataTable)
        table.border_title = (Text(f"Occurrences · {self.last_count.study['frequencies'][index]['word']}")
                              if index is not None else "Source context")
        table.clear(columns=True)
        budget = self.result_width(4)
        side_width = min(9, max(3, budget // 7))
        occurrence_width = min(10, max(4, budget // 6))
        table.add_column("Side", width=side_width)
        table.add_column("Occurrence", width=occurrence_width)
        where_width = min(30, max(6, budget // 4))
        table.add_column("Where", width=where_width)
        table.add_column("In context", width=max(1, budget - side_width - occurrence_width - where_width))
        self.shown_sources = () if index is None else tuple(words.sources(self.last_count, index))
        self.query_one("#sources-label", Static).update(SOURCES_HELP if index is not None else "No word selected")
        for item in self.shown_sources:
            label = item["label"].replace(" | p. ", "\np. ")
            table.add_row(item["side"], f"{item['number']} of {item['count']}" if item["number"]
                          else f"{item['count']} here", Text(label, overflow="fold"),
                          in_context(item["context"]), height=None)
        if index is not None:
            row = self.last_count.study["frequencies"][index]
            total = sum(row[side]["count"] for side in ("target", "reference") if row[side] is not None)
            # Fewer rows than occurrences: the list was cut short, or some
            # passage's later occurrences could not be confirmed.
            self.query_one("#sources-label", Static).update(SOURCES_HELP if len(self.shown_sources) == total else
                f"Listing {len(self.shown_sources):,} of {total:,} occurrences. " + SOURCES_HELP)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if (event.data_table.id == "frequencies" and self.last_count is not None
                and isinstance(self.last_count, words.Count)):
            self.show_sources(int(event.row_key.value))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "frequencies":
            if isinstance(self.last_count, tfidf.TfidfCount):
                source = tfidf.source(self.last_count, event.cursor_row)
                if source is None:
                    self.query_one("#result-status", Static).update("A text file cannot be opened in the reader.")
                else:
                    self.open_in_reader(source)
                return
            if isinstance(self.last_count, sentences.SentenceCount):
                if not 0 <= event.cursor_row < len(self.last_count.study["longest"][:sentences.ROW_LIMIT]):
                    return
                source = sentences.source(self.last_count, event.cursor_row)
                if source is None:
                    self.query_one("#result-status", Static).update("A text file's sentences cannot be opened in the reader.")
                else:
                    self.open_in_reader(source)
                return
            self.query_one("#sources", DataTable).focus()
            return
        if event.data_table.id != "sources" or not 0 <= event.cursor_row < len(self.shown_sources):
            return
        source = self.shown_sources[event.cursor_row]["open"]
        if source is None:
            self.query_one("#result-status", Static).update("A text file's words cannot be opened in the reader.")
            return
        self.open_in_reader(source)

    def open_in_reader(self, source) -> None:
        """Ask the reader, through Neovim's terminal, to open a source."""
        request = json.dumps({"version": 1, "op": "open_source", "source": source},
                             ensure_ascii=True, separators=(",", ":"))
        encoded = base64.b64encode(request.encode("ascii")).decode("ascii")
        # Textual's own driver writes the sequence between frames, as it does
        # for its clipboard sequence, so it never splits a screen update.
        if self._driver is not None:
            self._driver.write(self.SOURCE_SEQUENCE.format(encoded))
        self.query_one("#result-status", Static).update("Asked the reader to open this passage.")

    @work(thread=True, exclusive=True, group="export")
    def export_table(self, count, table_format) -> None:
        try:
            outcome = words.export(count, table_format)
        except (words.EngineMissing, ValueError, OSError) as error:
            outcome = error
        try:
            self.call_from_thread(self.finish_export, count, outcome)
        except RuntimeError:
            pass

    def finish_export(self, count, outcome) -> None:
        if count is not self.last_count:
            return
        for button in self.query("#export-row Button"):
            button.disabled = False
        self.query_one("#result-status", Static).update(
            f"Not exported: {outcome}" if isinstance(outcome, Exception) else f"Exported: {outcome}")

    def on_resize(self, event) -> None:
        # App.size is updated by Textual after this handler; use the event's
        # destination width so the breakpoint changes on this resize.
        self.update_layout(event.size.width)
        if self.last_count is not None:
            self.call_after_refresh(self.reflow_result)

    def update_layout(self, width=None) -> None:
        """Reflow existing widgets without replacing controls or their state."""
        width = self.size.width if width is None else width
        # Keep the underlying workspace in sync while the sort menu is open.
        for screen in self.screen_stack:
            screen.set_class(width < 100, "-compact")
            screen.set_class(width < 60, "-small")

    def reflow_result(self) -> None:
        table = self.query_one("#frequencies", DataTable)
        screen = self.query_one("#screens", TabbedContent).active
        focused = self.focused
        row = table.cursor_row
        word_index = (self.word_order[row] if isinstance(self.last_count, words.Count)
                      and row < len(self.word_order) else None)
        sources = self.query_one("#sources", DataTable)
        source_row = sources.cursor_row
        export_disabled = [button.disabled for button in self.query("#export-row Button")]
        messages = [(widget, widget.content) for widget in
                    (self.query_one("#status", Static), self.query_one("#result-status", Static))]
        # Rebuilding posts highlight events for row zero. Suppress those
        # intermediate events so they cannot reset the restored occurrence.
        with self.prevent(DataTable.RowHighlighted):
            self.show_result(self.last_count, self.last_saved)
            if word_index is not None:
                row = self.word_order.index(word_index) if word_index in self.word_order else 0
            table.move_cursor(row=row)
            if isinstance(self.last_count, words.Count):
                self.show_sources(self.word_order[row] if table.row_count else None)
                sources.move_cursor(row=source_row)
        for button, disabled in zip(self.query("#export-row Button"), export_disabled):
            button.disabled = disabled
        for widget, content in messages:
            widget.update(content)
        self.query_one("#screens", TabbedContent).active = screen
        if focused is not None and focused.display:
            focused.focus()

    def on_key(self, event) -> None:
        if isinstance(self.screen, WordSort):
            return
        active = self.query_one("#screens", TabbedContent).active
        if active == "results" and self.last_count is not None:
            field = self.query_one("#word-filter", Input)
            if self.focused is field:
                if event.key == "escape":
                    if field.value:
                        field.value = ""
                    else:
                        self.query_one("#frequencies").focus()
                    event.stop()
                    event.prevent_default()
                return
            if event.key == "i":
                self.toggle_details()
                event.stop()
            if event.key in ("slash", "/", "ctrl+f") and isinstance(self.last_count, words.Count):
                field.focus()
                event.stop()
                event.prevent_default()
            if event.key == "escape" and self.focused is self.query_one("#summary-box"):
                self.query_one("#frequencies").focus()
                event.stop()
        if (event.key == "s" and active == "results"
                and self.focused is self.query_one("#frequencies", DataTable)
                and isinstance(self.last_count, words.Count) and self.last_count.comparison is not None):
            self.push_screen(WordSort(self.word_sort), self.sort_words)
            event.stop()
        if event.key == "escape" and active in BROWSERS:
            self.query_one(f"#{active}-list").focus()
            event.stop()
        if event.key == "escape" and self.focused is self.query_one("#sources", DataTable):
            self.query_one("#frequencies", DataTable).focus()
            event.stop()

    def sort_words(self, choice) -> None:
        if choice is not None:
            self.word_sort = choice
            self.reflow_result()

    def follow_reader_theme(self) -> None:
        """Take the theme the reader last wrote; anything unreadable or unknown is ignored."""
        try:
            with open(self.theme_file, encoding="utf-8") as stream:
                name = stream.read(32).strip()
        except (OSError, UnicodeDecodeError):
            return
        if name in TEXTUAL_THEMES and self.theme != TEXTUAL_THEMES[name]:
            self.theme = TEXTUAL_THEMES[name]

    def on_mount(self) -> None:
        self.update_layout()
        for selector, title in {
            "encyclopedia-list": "Contents", "encyclopedia-detail": "Encyclopedia",
            "methods-list": "Available methods", "methods-detail": "Method",
            "study-panel": "Study", "experiment-body": "Experiment",
            "target-panel": "Target", "reference-group": "Compare with",
            "tfidf-settings": "TF-IDF settings", "summary-box": "Study summary",
            "frequencies": "Measurements", "sources": "Source context",
            "overall": "Overall terms", "empty-results": "Results",
        }.items():
            self.query_one(f"#{selector}").border_title = title
        self.update_choices()
        self.update_method_action(self.query_one("#methods-list", OptionList).highlighted or 0)
        self.query_one("#word-filter").tooltip = "Filter normalized word spellings; counts, denominators and exports retain the full study."
        self.set_word_widgets(False)
        if self.theme_file:
            # A stat-sized read twice a second; T in the reader shows here within half a second.
            self.set_interval(0.5, self.follow_reader_theme)
        screen = self.state.get("screen")
        self.action_screen(screen if screen in SCREENS else "encyclopedia")

    def action_screen(self, name: str) -> None:
        # Let go of focus first: a focused widget on the old screen would pull
        # it back to the front.
        self.set_focus(None)
        self.query_one("#screens", TabbedContent).active = name
        # Then start on the screen's first control.
        first = {"encyclopedia": "#encyclopedia-list", "methods": "#methods-list", "experiment": "#study",
                 "results": "#frequencies" if self.last_count is not None else "#configure"}.get(name)
        if first:
            self.query_one(first).focus()

    def action_leave(self) -> None:
        self.count_serial += 1  # A count still running is abandoned.
        if self.state_file:
            save_state(self.state_file, {
                "version": 1, "screen": self.query_one("#screens", TabbedContent).active,
                "origin": self.context["reference"]["reference"]["target_id"]})
        self.exit(0)
