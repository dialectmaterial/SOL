"""ESSENCE interface: four logical screens and reproducible lexical studies.

Neovim owns the outer layout (beside the reader or fullscreen, Alt-F, and
Alt-R back to the reader); this app owns only what is inside its window.
Leaving saves which screen was open and for which passage, nothing else.
"""
from __future__ import annotations

import base64
import json

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
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
from sol.reader.options import DEFAULT_READER_THEME

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
    "encyclopedia": "Encyclopedia · arrows browse · Enter reads (on Genealogy, moves through the map) · "
                    "Escape returns to the list. Links open only when selected.",
    "methods": "What ESSENCE runs: inputs, settings, output, limits and the command line · arrows browse · "
               "Enter reads · Escape returns to the list.",
}

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


class EssenceApp(App):
    """One investigation, shown in whatever space Neovim gives it."""

    TITLE = "SOL ESSENCE"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    TabPane { padding: 1 1 0 1; }
    .browser-list { height: 11; max-height: 40%; border: none; background: $surface; padding: 1; }
    .browser-help { height: auto; padding: 0 0 1 0; color: $text-muted; }
    .browser-detail { height: 1fr; margin-top: 1; }
    #origin, #layout-hint { padding: 0 2; color: $text-muted; }
    Markdown { padding: 0 1; }
    #genealogy-map { height: auto; border: none; background: transparent; padding: 0 1; }
    .choices { height: auto; }
    .choice-group { height: auto; width: 1fr; margin-top: 1; }
    .section-label { color: $text-muted; text-style: bold; height: 1; }
    RadioSet { border: none; padding: 0; background: transparent; height: auto; }
    RadioButton { border: none; padding: 0 1; background: transparent; }
    RadioButton:focus { text-style: bold; }
    /* The chosen option's dot in the theme's accent; the others stay visible on dark pages. */
    RadioButton > .toggle--button { background: transparent; color: $text-muted; }
    RadioButton.-on > .toggle--button { color: $accent; }
    Input { margin-top: 1; }
    #run-row { height: auto; padding-top: 1; }
    Button { min-width: 12; height: 3; margin-right: 1; border: none; }
    #cancel { background: transparent; }
    #status { padding-top: 1; color: $text-muted; }
    #results { height: 1fr; }
    #summary { padding: 0; }
    #summary-box { height: auto; max-height: 20%; }
    #frequencies { height: 1fr; min-height: 3; }
    DataTable { background: $background; }
    #sources-label, #overall-label { color: $text-muted; height: auto; max-height: 2; }
    #sources { height: 1fr; min-height: 4; }
    #overall { height: 1fr; min-height: 3; max-height: 30%; }
    #export-row { height: 1; }
    #export-row Button { height: 1; }
    #result-status { color: $text-muted; height: auto; }
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

    def compose(self) -> ComposeResult:
        target = self.context["reference"]["reference"]["target_id"]
        yield Static(f"From the reader: {self.context['label']} · record {target[:8]}", id="origin")
        with Vertical():
            with TabbedContent(id="screens"):
                for name, (label, text) in SCREENS.items():
                    with TabPane(label, id=name):
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

    # Encyclopedia and Methods: a list of entries above the highlighted one's text.
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
        # The encyclopedia opens on its genealogy, a map of where the methods come from.
        first = ["Genealogy"] if name == "encyclopedia" else []
        yield OptionList(*first, *(item["title"] for item in self.browser_items(name)), id=f"{name}-list",
                         classes="browser-list")
        with VerticalScroll(id=f"{name}-detail", classes="browser-detail"):
            yield Markdown(self.browser_markdown(name, 0), id=f"{name}-entry")
            if name == "encyclopedia":
                yield OptionList(*self.genealogy_options(), id="genealogy-map")
                yield Markdown(self.genealogy_sources(), id="genealogy-sources")

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
        with VerticalScroll(can_focus=False):
            yield Label("Choose a study and its source.", classes="browser-help")
            yield Label("Study", classes="section-label")
            with RadioSet(id="study"):
                yield RadioButton("Word frequencies", value=True, name="words")
                yield RadioButton("Sentence lengths", name="sentences")
                yield RadioButton("TF-IDF · top terms by passage", name="tfidf")
            with Horizontal(classes="choices"):
                with Vertical(classes="choice-group"):
                    yield Label("Target", classes="section-label")
                    with RadioSet(id="target"):
                        for key, label in words.TARGETS.items():
                            yield RadioButton(label, value=key == "passage", name=key)
                with Vertical(id="reference-group", classes="choice-group"):
                    yield Label("Compare with", classes="section-label")
                    with RadioSet(id="reference"):
                        for key, label in words.REFERENCES.items():
                            yield RadioButton(label, value=key == "none", name=key)
            yield Input(placeholder="Target file · UTF-8 path", id="target-file")
            yield Input(placeholder="Reference file · UTF-8 path", id="reference-file")
            with Horizontal(id="run-row"):
                yield Button("Run study", id="run")
                yield Button("Cancel", id="cancel", disabled=True)
            yield Static("", id="status")

    def compose_results(self) -> ComposeResult:
        # Denominators, formulas and warnings can run long; they scroll so the
        # table keeps most of the height.
        with VerticalScroll(id="summary-box"):
            yield Static("Nothing yet. Choose a study and a target in Experiment, then press Run.", id="summary")
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
        self.query_one("#reference-group").display = comparison
        self.query_one("#target-file").display = self.choice("target") == "file"
        self.query_one("#reference-file").display = comparison and self.choice("reference") == "file"

    count_serial = 0
    last_count = None
    shown_sources = ()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            # Read the choices here, on the interface thread; each count has a
            # number, and only the latest one may save or show anything.
            self.count_serial += 1
            self.query_one("#status", Static).update("Counting…")
            self.query_one("#cancel", Button).disabled = False
            self.count_words(self.count_serial, self.choice("target"), self.choice("reference"),
                             self.query_one("#target-file", Input).value,
                             self.query_one("#reference-file", Input).value, self.choice("study"))
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
    def count_words(self, serial, target, reference, target_file, reference_file, study="words") -> None:
        # The engine reads the corpus or files; keep the interface responsive.
        try:
            if study == "tfidf":
                outcome = tfidf.run(self.context, target, target_file=target_file)
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
        if isinstance(count, tfidf.TfidfCount):
            return self.show_tfidf(count, saved)
        if isinstance(count, sentences.SentenceCount):
            return self.show_sentences(count, saved)
        self.set_word_widgets(True)
        table = self.query_one("#frequencies", DataTable)
        table.clear(columns=True)
        columns = [("Target", 6), ("per 10k", 8)]
        if count.reference is not None:
            columns += [("Reference", 9), ("per 10k", 8)]
        if count.comparison is not None:
            columns += [("Difference", 10), ("Log₂ ratio", 10)]
        budget = self.result_width(len(columns) + 1)
        table.add_column("Word", width=max(1, budget - sum(width for _, width in columns)))
        for label, width in columns:
            table.add_column(label, width=width)
        shown, total = words.rows(count)
        for row in shown:
            cells = row if count.reference is not None else row[:3]
            table.add_row(*cells, height=None)
        lines = words.summary(count)
        if len(shown) < total:
            lines.append(f"Showing the {len(shown):,} most frequent of {total:,} words.")
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
        self.show_sources(0 if total else None)
        self.query_one("#screens", TabbedContent).active = "results"
        # Words first: arrows choose a word, Enter goes to its sources.
        table.focus()

    def result_width(self, columns):
        """Cell budget: pane padding, scrollbar, then DataTable cell padding.

        Use the viewport, never content widths, so a resize cannot make long
        words, paths or undefined measures force sideways scrolling.
        """
        return max(columns, self.size.width - 4 - 2 * columns)

    def set_word_widgets(self, shown) -> None:
        self.query_one("#overall").display = False
        self.query_one("#overall-label").display = False
        # Sources and export belong to word counts only.
        for selector in ("#sources-label", "#sources", "#export-row"):
            self.query_one(selector).display = shown

    def show_sentences(self, count, saved) -> None:
        self.set_word_widgets(False)
        table = self.query_one("#frequencies", DataTable)
        table.clear(columns=True)
        table.add_column("Words", width=7)
        table.add_column("Beginning", width=self.result_width(3) - 7 - 24)
        table.add_column("Where", width=24)
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
        table.clear(columns=True)
        table.add_column("Side", width=9)
        table.add_column("Occurrence", width=10)
        where_width = min(30, self.result_width(4) // 4)
        table.add_column("Where", width=where_width)
        table.add_column("In context", width=self.result_width(4) - 19 - where_width)
        self.shown_sources = () if index is None else tuple(words.sources(self.last_count, index))
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
            self.show_sources(event.cursor_row)

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

    def on_resize(self) -> None:
        if self.last_count is not None:
            self.call_after_refresh(self.reflow_result)

    def reflow_result(self) -> None:
        table = self.query_one("#frequencies", DataTable)
        screen = self.query_one("#screens", TabbedContent).active
        focused = self.focused
        row = table.cursor_row
        sources = self.query_one("#sources", DataTable)
        source_row = sources.cursor_row
        export_disabled = [button.disabled for button in self.query("#export-row Button")]
        messages = [(widget, widget.content) for widget in
                    (self.query_one("#status", Static), self.query_one("#result-status", Static))]
        # Rebuilding posts highlight events for row zero. Suppress those
        # intermediate events so they cannot reset the restored occurrence.
        with self.prevent(DataTable.RowHighlighted):
            self.show_result(self.last_count, self.last_saved)
            table.move_cursor(row=row)
            if isinstance(self.last_count, words.Count):
                self.show_sources(row if table.row_count else None)
                sources.move_cursor(row=source_row)
        for button, disabled in zip(self.query("#export-row Button"), export_disabled):
            button.disabled = disabled
        for widget, content in messages:
            widget.update(content)
        self.query_one("#screens", TabbedContent).active = screen
        if focused is not None and focused.display:
            focused.focus()

    def on_key(self, event) -> None:
        active = self.query_one("#screens", TabbedContent).active
        if event.key == "escape" and active in BROWSERS:
            self.query_one(f"#{active}-list").focus()
            event.stop()
        if event.key == "escape" and self.focused is self.query_one("#sources", DataTable):
            self.query_one("#frequencies", DataTable).focus()
            event.stop()

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
        self.update_choices()
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
        first = {"encyclopedia": "#encyclopedia-list", "methods": "#methods-list", "experiment": "#study", "results": "#frequencies"}.get(name)
        if first:
            self.query_one(first).focus()

    def action_leave(self) -> None:
        self.count_serial += 1  # A count still running is abandoned.
        if self.state_file:
            save_state(self.state_file, {
                "version": 1, "screen": self.query_one("#screens", TabbedContent).active,
                "origin": self.context["reference"]["reference"]["target_id"]})
        self.exit(0)
