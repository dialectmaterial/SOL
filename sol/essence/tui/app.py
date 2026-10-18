"""ESSENCE interface shell (stage 1): four logical screens, mock content.

Neovim owns the outer layout (beside the reader or fullscreen, Alt-F, and
Alt-R back to the reader); this app owns only what is inside its window.
Leaving saves which screen was open and for which passage, nothing else.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Markdown, Static, TabbedContent, TabPane

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
    "experiment": ("Experiment", """\
## Experiment

*Next (stage 2):* word frequencies for a **target** (this passage, its
section, the book) against an optional **reference**, with denominators.
"""),
    "results": ("Results", """\
## Results

*Next (stage 2):* counts and rates, each row linked to its source passage,
which opens in the reader.
"""),
}


class EssenceApp(App):
    """One investigation, shown in whatever space Neovim gives it."""

    TITLE = "SOL ESSENCE"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    #origin { padding: 0 1; color: $text-muted; }
    #layout-hint { padding: 0 1; color: $text-muted; }
    Markdown { padding: 0 1; }
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
                        yield Markdown(text)
        yield Static("Alt-F fullscreen ⇄ beside the reader · Alt-R back to the reader · 1–4 screens",
                     id="layout-hint")
        yield Footer()

    def on_mount(self) -> None:
        screen = self.state.get("screen")
        if screen in SCREENS:
            self.query_one("#screens", TabbedContent).active = screen

    def action_screen(self, name: str) -> None:
        self.query_one("#screens", TabbedContent).active = name

    def action_leave(self) -> None:
        if self.state_file:
            save_state(self.state_file, {
                "version": 1, "screen": self.query_one("#screens", TabbedContent).active,
                "origin": self.context["reference"]["reference"]["target_id"]})
        self.exit(0)
