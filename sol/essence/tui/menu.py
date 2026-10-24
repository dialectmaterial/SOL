"""The study menu: every choice visible with its current value, one key each.

Modelled on magit's Transient menus. Study, target and reference are single
keys; the chosen ones are marked; Enter runs. File paths and TF-IDF's
top_n appear only when the choices need them. The menu runs nothing itself:
it posts `StudyMenu.Run`, and the app counts.
"""
from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label, Static

from sol.essence.tui import words

STUDIES = {"words": "words", "sentences": "sentences", "tfidf": "TF-IDF"}
STUDY_KEYS = {"words": "w", "sentences": "s", "tfidf": "t"}
TARGET_KEYS = {"passage": "p", "section": "c", "book": "b", "file": "f"}
REFERENCE_KEYS = {"none": "0", "section": "C", "book": "B", "file": "F"}
SCOPES = {"passage": "this passage", "section": "this section", "book": "the whole book", "file": "a text file"}
NOTES = {
    "words": "Counts words, with their occurrences; with a reference, compares rates. "
             "Counts describe lexical patterns; they do not identify concepts.",
    "sentences": "Measures sentence lengths, their distribution and place in the paragraph. "
                 "Punctuation rules describe the selected translation's sentences.",
    "tfidf": "Ranks terms within each passage and across the source. "
             "Weights depend on the chosen documents; they do not establish conceptual significance.",
}


class StudyMenu(Vertical, can_focus=True):
    """Choose a study and its sources; Enter runs it."""

    class Run(Message):
        """The reader of the menu asked for the chosen study to run."""

    class Close(Message):
        """Escape: put the menu away without running anything."""

    class Changed(Message):
        """A choice changed; the header and the method shown follow it."""

    BINDINGS = [
        *(Binding(key, f"choose('study', '{name}')", STUDIES[name], show=False)
          for name, key in STUDY_KEYS.items()),
        *(Binding(key, f"choose('target', '{name}')", name, show=False) for name, key in TARGET_KEYS.items()),
        *(Binding(key, f"choose('reference', '{name}')", name, show=False) for name, key in REFERENCE_KEYS.items()),
        Binding("n", "top_n", "top terms", show=False),
        Binding("enter", "run", "Run"),
        Binding("escape", "close", "Close"),
    ]

    def __init__(self, **options):
        super().__init__(**options)
        self.study, self.target, self.reference = "words", "passage", "none"

    def compose(self):
        yield Static("", id="menu-choices")
        with Horizontal(id="target-file-row", classes="menu-field"):
            yield Label("f  file ")
            yield Input(placeholder="UTF-8 path", id="target-file")
        with Horizontal(id="reference-file-row", classes="menu-field"):
            yield Label("F  reference ")
            yield Input(placeholder="UTF-8 path", id="reference-file")
        with Horizontal(id="tfidf-settings", classes="menu-field"):
            yield Label("n  top terms (1–1,000) ")
            yield Input("20", id="top-n", placeholder="1–1,000", type="integer")
        yield Static("", id="menu-summary")
        yield Static("", id="status")

    def on_mount(self):
        self.refresh_menu()

    def choice(self, name):
        return getattr(self, name)

    def set_choices(self, **choices):
        for name, value in choices.items():
            setattr(self, name, value)
        self.refresh_menu()

    def refresh_menu(self):
        width = self.app.size.width
        self.query_one("#menu-choices", Static).update(self.choices_text(width))
        words_study = self.study == "words"
        self.query_one("#target-file-row").display = self.target == "file"
        self.query_one("#reference-file-row").display = words_study and self.reference == "file"
        self.query_one("#tfidf-settings").display = self.study == "tfidf"
        self.query_one("#menu-summary", Static).update(self.summary())
        self.post_message(self.Changed())

    def choices_text(self, width):
        """Three columns of keyed choices, or three stacked groups when narrow."""
        groups = [("Study", [(STUDY_KEYS[name], label, self.study == name, "study", name)
                             for name, label in STUDIES.items()]),
                  ("Target", [(TARGET_KEYS[name], label.lower(), self.target == name, "target", name)
                              for name, label in words.TARGETS.items()])]
        if self.study == "words":
            groups.append(("Compare with", [(REFERENCE_KEYS[name], label.lower() if name != "none" else "none",
                                             self.reference == name, "reference", name)
                                            for name, label in words.REFERENCES.items()]))
        text = Text()
        if width >= 66:
            column = 22
            text.append("".join(title.ljust(column + 2) for title, _ in groups).rstrip() + "\n", style="bold")
            for row in range(4):
                for title, items in groups:
                    if row < len(items):
                        self.append_item(text, items[row], column)
                    else:
                        text.append(" " * (column + 2))
                text.append("\n")
        else:
            for title, items in groups:
                text.append(title + "\n", style="bold")
                for item in items:
                    self.append_item(text, item, 0)
                    text.append("\n")
        return text

    @staticmethod
    def append_item(text, item, column):
        key, label, chosen, group, name = item
        start = len(text)
        text.append(f" {key} ", style="bold reverse" if chosen else "bold")
        text.append(" " + label + (" ●" if chosen else ""), style="bold" if chosen else "")
        if column:
            text.append(" " * max(1, column + 2 - (len(text) - start)))
        text.stylize(Style(meta={"@click": f"choose('{group}','{name}')"}), start, len(text))

    def summary(self):
        target = SCOPES[self.target]
        if self.study == "words":
            plan = (f"Will count the words of {target}." if self.reference == "none" else
                    f"Will compare word rates in {target} with {SCOPES[self.reference]}.")
        elif self.study == "sentences":
            plan = f"Will measure the sentences of {target}."
        else:
            plan = f"Will rank the top terms of each passage in {target}."
        line = Text(plan + "  ", style="bold")
        line.append("Enter runs · Esc closes · ? keys\n", style="dim")
        line.append(NOTES[self.study], style="dim")
        return line

    # Actions -------------------------------------------------------------------
    def action_choose(self, group, name):
        if group == "reference" and self.study != "words":
            return
        setattr(self, group, name)
        self.refresh_menu()
        field = {"target": "#target-file", "reference": "#reference-file"}.get(group)
        if name == "file" and field is not None:
            self.query_one(field).focus()

    def action_top_n(self):
        if self.study == "tfidf":
            self.query_one("#top-n").focus()

    def action_run(self):
        self.post_message(self.Run())

    def action_close(self):
        self.post_message(self.Close())

    def on_input_submitted(self, event):
        event.stop()
        self.post_message(self.Run())

    def on_key(self, event):
        # Escape in a field returns to the choices; a second Escape closes.
        if event.key == "escape" and isinstance(self.app.focused, Input) and self.app.focused in self.query(Input):
            self.focus()
            event.stop()
            event.prevent_default()
