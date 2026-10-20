"""ESSENCE interface: four logical screens, word counts and comparison.

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
from textual import work
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (Button, DataTable, Footer, Input, Label, Markdown, OptionList, RadioButton, RadioSet, Static,
                             TabbedContent, TabPane)

from sol.essence.encyclopedia import entry_markdown, load_catalog
from sol.essence.tui import sentences, words
from sol.essence.tui.context import load_state, save_state
from sol.reader.options import DEFAULT_READER_THEME

TEXTUAL_THEMES = {"mocha": "catppuccin-mocha", "latte": "catppuccin-latte", "terminal": "ansi-dark"}

SOURCES_HELP = ("Every occurrence of the highlighted word: Enter on a word comes here, Enter here opens it "
                "in the reader (Alt-Left there returns to where you were), Escape goes back to the words.")

SCREENS = {
    "encyclopedia": ("Encyclopedia", None),
    "methods": ("Methods", """\
## Methods

*Not built yet (stage 5).* What can run on this machine: tasks such as
tokenization, tagging or embedding, and the installed implementations.
"""),
    "experiment": ("Experiment", None),
    "results": ("Results", None),
}


def in_context(context):
    """The words around an occurrence, the word itself in bold."""
    if context is None:
        return Text("(the text has changed since the count)", style="dim")
    return Text.assemble(context["left"], (context["word"], "bold"), context["right"])


class EssenceApp(App):
    """One investigation, shown in whatever space Neovim gives it."""

    TITLE = "SOL ESSENCE"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    #encyclopedia-list { height: 7; }
    #encyclopedia-help { height: auto; padding: 0 1; }
    #encyclopedia-detail { height: 1fr; }
    #origin { padding: 0 1; color: $text-muted; }
    #layout-hint { padding: 0 1; color: $text-muted; }
    Markdown { padding: 0 1; }
    .choices { height: auto; }
    .choices RadioSet { width: 1fr; }
    #run-row { height: auto; padding: 1 0 0 0; }
    #status, #summary { padding: 0 1; }
    #summary-box { height: auto; max-height: 8; }
    #frequencies { height: 1fr; min-height: 6; }
    #sources-label { padding: 1 1 0 1; color: $text-muted; }
    #sources { height: 8; }
    #export-row { height: auto; }
    #result-status { padding: 0 1; }
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
        # Textual's own Catppuccin themes; Terminal uses the terminal's ANSI colors.
        self.theme = TEXTUAL_THEMES[theme]
        self.theme_file = theme_file
        self.catalog = load_catalog()
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
                        if name == "encyclopedia":
                            yield from self.compose_encyclopedia()
                        elif name == "experiment":
                            yield from self.compose_experiment()
                        elif name == "results":
                            yield from self.compose_results()
                        else:
                            yield Markdown(text)
        yield Static("Alt-F fullscreen ⇄ beside the reader · Alt-R back to the reader · 1–4 screens",
                     id="layout-hint")
        yield Footer()

    def compose_encyclopedia(self) -> ComposeResult:
        yield Static("Methods · arrows browse · Enter reads · Escape returns to the list. "
                     "Links open only when selected.", id="encyclopedia-help")
        yield OptionList(*(item["title"] for item in self.catalog["entries"]), id="encyclopedia-list")
        with VerticalScroll(id="encyclopedia-detail"):
            yield Markdown(entry_markdown(self.catalog, self.catalog["entries"][0]), id="encyclopedia-entry")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "encyclopedia-list":
            self.query_one("#encyclopedia-entry", Markdown).update(
                entry_markdown(self.catalog, self.catalog["entries"][event.option_index]))
            self.query_one("#encyclopedia-detail", VerticalScroll).scroll_home(animate=False)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "encyclopedia-list":
            self.query_one("#encyclopedia-detail").focus()

    def compose_experiment(self) -> ComposeResult:
        # Tab goes straight to the choices, not to the scrolling container.
        with VerticalScroll(can_focus=False):
            yield Label("Count the words of a target, optionally against a reference, or measure its "
                        "sentence lengths (no reference).")
            with RadioSet(id="study"):
                yield RadioButton("Word frequencies", value=True, name="words")
                yield RadioButton("Sentence lengths", name="sentences")
            with Horizontal(classes="choices"):
                with RadioSet(id="target"):
                    for key, label in words.TARGETS.items():
                        yield RadioButton(f"Target: {label}", value=key == "passage", name=key)
                with RadioSet(id="reference"):
                    for key, label in words.REFERENCES.items():
                        yield RadioButton(f"Reference: {label}", value=key == "none", name=key)
            yield Input(placeholder="Target text file (UTF-8), when 'A text file' is chosen", id="target-file")
            yield Input(placeholder="Reference text file (UTF-8), when 'A text file' is chosen", id="reference-file")
            with Horizontal(id="run-row"):
                yield Button("Run", id="run", variant="primary")
                yield Button("Cancel", id="cancel", disabled=True)
            yield Static("", id="status")

    def compose_results(self) -> ComposeResult:
        # Denominators, formulas and warnings can run long; they scroll so the
        # table keeps most of the height.
        with VerticalScroll(id="summary-box"):
            yield Static("Nothing yet. Choose a study and a target in Experiment, then press Run.", id="summary")
        yield DataTable(id="frequencies", zebra_stripes=True, cursor_type="row")
        yield Static(SOURCES_HELP, id="sources-label")
        yield DataTable(id="sources", cursor_type="row")
        with Horizontal(id="export-row"):
            yield Button("Export CSV", id="export-csv", disabled=True)
            yield Button("Export TSV", id="export-tsv", disabled=True)
        yield Static("", id="result-status")

    def choice(self, name: str) -> str:
        pressed = self.query_one(f"#{name}", RadioSet).pressed_button
        return pressed.name if pressed is not None else {"target": "passage", "study": "words"}.get(name, "none")

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
            if study == "sentences":
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
            module = sentences if isinstance(outcome, sentences.SentenceCount) else words
            saved = module.save(outcome) if self.state_file else None
        except (words.EngineMissing, ValueError, OSError) as error:
            status.update(f"Counted, but not saved: {error}")
            saved = None
        self.show_result(outcome, saved)

    def show_result(self, count, saved) -> None:
        if isinstance(count, sentences.SentenceCount):
            return self.show_sentences(count, saved)
        self.set_word_widgets(True)
        table = self.query_one("#frequencies", DataTable)
        table.clear(columns=True)
        table.add_columns("Word", "Target", "per 10,000", "Reference", "per 10,000",
                          *(("Difference", "Log₂ ratio") if count.comparison is not None else ()))
        shown, total = words.rows(count)
        table.add_rows(shown)
        lines = words.summary(count)
        if len(shown) < total:
            lines.append(f"Showing the {len(shown):,} most frequent of {total:,} words.")
        lines.append(f"Saved: {saved} (check with: sol analyze check FILE)" if saved else
                     "Not saved: this reader session has no workspace.")
        self.query_one("#summary", Static).update("\n".join(lines))
        self.query_one("#result-status", Static).update("")
        self.query_one("#status", Static).update(f"Counted {total:,} distinct words; see Results (4).")
        self.last_count = count
        for button in self.query("#export-row Button"):
            button.disabled = count.reference is None
        self.show_sources(0 if total else None)
        self.query_one("#screens", TabbedContent).active = "results"
        # Words first: arrows choose a word, Enter goes to its sources.
        table.focus()

    def set_word_widgets(self, shown) -> None:
        # Sources and export belong to word counts only.
        for selector in ("#sources-label", "#sources", "#export-row"):
            self.query_one(selector).display = shown

    def show_sentences(self, count, saved) -> None:
        self.set_word_widgets(False)
        table = self.query_one("#frequencies", DataTable)
        table.clear(columns=True)
        table.add_columns("Words", "Beginning", "Where")
        table.add_rows(sentences.rows(count))
        lines = sentences.summary(count)
        if count.study["longest"]:
            lines.append("The longest sentences are below; Enter opens one in the reader (Alt-Left there returns).")
        lines.append(f"Saved: {saved} (check with: sol analyze check FILE)" if saved else
                     "Not saved: this reader session has no workspace.")
        self.query_one("#summary", Static).update("\n".join(lines))
        self.query_one("#result-status", Static).update("")
        self.query_one("#status", Static).update(
            f"Measured {count.study['summary']['sentences']:,} sentences; see Results (4).")
        self.last_count = count
        self.shown_sources = ()
        self.query_one("#screens", TabbedContent).active = "results"
        table.focus()

    def show_sources(self, index) -> None:
        table = self.query_one("#sources", DataTable)
        table.clear(columns=True)
        table.add_columns("Side", "Occurrence", "In context", "Where")
        self.shown_sources = () if index is None else tuple(words.sources(self.last_count, index))
        table.add_rows([(item["side"], f"{item['number']} of {item['count']}" if item["number"]
                         else f"{item['count']} here", in_context(item["context"]),
                         item["label"] + ("" if item["open"] else " (not in the reader)"))
                        for item in self.shown_sources])
        if index is not None:
            row = self.last_count.study["frequencies"][index]
            total = sum(row[side]["count"] for side in ("target", "reference") if row[side] is not None)
            # Fewer rows than occurrences: the list was cut short, or some
            # passage's later occurrences could not be confirmed.
            self.query_one("#sources-label", Static).update(SOURCES_HELP if len(self.shown_sources) == total else
                f"Listing {len(self.shown_sources):,} of {total:,} occurrences. " + SOURCES_HELP)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if (event.data_table.id == "frequencies" and self.last_count is not None
                and not isinstance(self.last_count, sentences.SentenceCount)):
            self.show_sources(event.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "frequencies":
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

    def on_key(self, event) -> None:
        if (event.key == "escape"
                and self.query_one("#screens", TabbedContent).active == "encyclopedia"):
            self.query_one("#encyclopedia-list").focus()
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
        first = {"encyclopedia": "#encyclopedia-list", "experiment": "#study", "results": "#frequencies"}.get(name)
        if first:
            self.query_one(first).focus()

    def action_leave(self) -> None:
        self.count_serial += 1  # A count still running is abandoned.
        if self.state_file:
            save_state(self.state_file, {
                "version": 1, "screen": self.query_one("#screens", TabbedContent).active,
                "origin": self.context["reference"]["reference"]["target_id"]})
        self.exit(0)
