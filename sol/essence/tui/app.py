"""ESSENCE interface: four logical screens, word counts and comparison.

Neovim owns the outer layout (beside the reader or fullscreen, Alt-F, and
Alt-R back to the reader); this app owns only what is inside its window.
Leaving saves which screen was open and for which passage, nothing else.
"""
from __future__ import annotations

import base64
import json

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual import work
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (Button, DataTable, Footer, Input, Label, Markdown, RadioButton, RadioSet, Static,
                             TabbedContent, TabPane)

from sol.essence.tui import words
from sol.essence.tui.context import load_state, save_state

SCREENS = {
    "encyclopedia": ("Encyclopedia", """\
## Encyclopedia

*Not built yet (stage 4).* Historical entries on computational methods:
why each was made, what its authors found inadequate before it, what
trade-offs remain. Entries will be source-linked text, not screens.
"""),
    "methods": ("Methods", """\
## Methods

*Not built yet (stage 5).* What can run on this machine: tasks such as
tokenization, tagging or embedding, and the installed implementations.
"""),
    "experiment": ("Experiment", None),
    "results": ("Results", None),
}


class EssenceApp(App):
    """One investigation, shown in whatever space Neovim gives it."""

    TITLE = "SOL ESSENCE"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    #origin { padding: 0 1; color: $text-muted; }
    #layout-hint { padding: 0 1; color: $text-muted; }
    Markdown { padding: 0 1; }
    .choices { height: auto; }
    .choices RadioSet { width: 1fr; }
    #run-row { height: auto; padding: 1 0 0 0; }
    #status, #summary { padding: 0 1; }
    #frequencies { height: 1fr; }
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

    def __init__(self, context):
        super().__init__()
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
                        if name == "experiment":
                            yield from self.compose_experiment()
                        elif name == "results":
                            yield from self.compose_results()
                        else:
                            yield Markdown(text)
        yield Static("Alt-F fullscreen ⇄ beside the reader · Alt-R back to the reader · 1–4 screens",
                     id="layout-hint")
        yield Footer()

    def compose_experiment(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("Word frequencies: count the words of a target, optionally against a reference.")
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
                yield Button("Count words", id="run", variant="primary")
                yield Button("Cancel", id="cancel", disabled=True)
            yield Static("", id="status")

    def compose_results(self) -> ComposeResult:
        yield Static("No count yet. Choose a target in Experiment and press Count words.", id="summary")
        yield DataTable(id="frequencies", zebra_stripes=True, cursor_type="row")
        yield Static("Sources of the highlighted word. Enter opens one in the reader; "
                     "Alt-Left there returns to where you were.", id="sources-label")
        yield DataTable(id="sources", cursor_type="row")
        with Horizontal(id="export-row"):
            yield Button("Export CSV", id="export-csv", disabled=True)
            yield Button("Export TSV", id="export-tsv", disabled=True)
        yield Static("", id="result-status")

    def choice(self, name: str) -> str:
        pressed = self.query_one(f"#{name}", RadioSet).pressed_button
        return pressed.name if pressed is not None else ("passage" if name == "target" else "none")

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
                             self.query_one("#reference-file", Input).value)
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
    def count_words(self, serial, target, reference, target_file, reference_file) -> None:
        # The engine reads the corpus or files; keep the interface responsive.
        try:
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
            saved = words.save(outcome) if self.state_file else None
        except (words.EngineMissing, ValueError, OSError) as error:
            status.update(f"Counted, but not saved: {error}")
            saved = None
        self.show_result(outcome, saved)

    def show_result(self, count, saved) -> None:
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

    def show_sources(self, index) -> None:
        table = self.query_one("#sources", DataTable)
        table.clear(columns=True)
        table.add_columns("Side", "Count", "Where")
        self.shown_sources = () if index is None else tuple(words.sources(self.last_count, index))
        table.add_rows([(item["side"], str(item["count"]),
                         item["label"] + ("" if item["open"] else " (not in the reader)"))
                        for item in self.shown_sources])

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "frequencies" and self.last_count is not None:
            self.show_sources(event.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
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

    def on_mount(self) -> None:
        screen = self.state.get("screen")
        if screen in SCREENS:
            self.query_one("#screens", TabbedContent).active = screen

    def action_screen(self, name: str) -> None:
        self.query_one("#screens", TabbedContent).active = name

    def action_leave(self) -> None:
        self.count_serial += 1  # A count still running is abandoned.
        if self.state_file:
            save_state(self.state_file, {
                "version": 1, "screen": self.query_one("#screens", TabbedContent).active,
                "origin": self.context["reference"]["reference"]["target_id"]})
        self.exit(0)
