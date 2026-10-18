"""ESSENCE interface shell (stage 1): four logical screens, mock content.

Neovim owns the outer layout (beside the reader or fullscreen, Alt-F, and
Alt-R back to the reader); this app owns only what is inside its window.
Leaving saves which screen was open and for which passage, nothing else.
"""
from __future__ import annotations

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
    """
    BINDINGS = [
        Binding("q", "leave", "Leave ESSENCE"),
        Binding("ctrl+q", "leave", "Leave ESSENCE", show=False),
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
            yield Static("", id="status")

    def compose_results(self) -> ComposeResult:
        yield Static("No count yet. Choose a target in Experiment and press Count words.", id="summary")
        table = DataTable(id="frequencies", zebra_stripes=True, cursor_type="row")
        table.add_columns("Word", "Target", "per 10,000", "Reference", "per 10,000")
        yield table

    def choice(self, name: str) -> str:
        pressed = self.query_one(f"#{name}", RadioSet).pressed_button
        return pressed.name if pressed is not None else ("passage" if name == "target" else "none")

    count_serial = 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            # Read the choices here, on the interface thread; each count has a
            # number, and only the latest one may save or show anything.
            self.count_serial += 1
            self.query_one("#status", Static).update("Counting…")
            self.count_words(self.count_serial, self.choice("target"), self.choice("reference"),
                             self.query_one("#target-file", Input).value,
                             self.query_one("#reference-file", Input).value)

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

    def show_result(self, result, saved) -> None:
        table = self.query_one("#frequencies", DataTable)
        table.clear()
        shown, total = words.rows(result)
        table.add_rows(shown)
        lines = words.summary(result)
        if len(shown) < total:
            lines.append(f"Showing the {len(shown):,} most frequent of {total:,} words.")
        lines.append(f"Saved: {saved} (check with: sol analyze check FILE)" if saved else
                     "Not saved: this reader session has no workspace.")
        self.query_one("#summary", Static).update("\n".join(lines))
        self.query_one("#status", Static).update(f"Counted {total:,} distinct words; see Results (4).")
        self.last_result = result
        self.query_one("#screens", TabbedContent).active = "results"

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
