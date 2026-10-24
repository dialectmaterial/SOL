"""ESSENCE's result views: one widget per study, drawn for the space it gets.

Each view takes the engine's count and shows it at two sizes: beside the
reader (a tall, narrow column, the views stacked) and fullscreen (panes side
by side, details always shown). Views change only presentation; counts,
denominators, saved artifacts and exports always keep the whole study.
A view asks the app to open a source in the reader with `OpenSource`, and
reports what happened with `Status`.
"""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, OptionList, Static

from sol.essence.tui import sentences, tfidf, views, words

# Fullscreen from this many columns: panes side by side, details always shown.
WIDE = 150
WORDS_PANE = 86  # columns of the word table when panes sit side by side
DETAILS_PANE = 40
SHORT_UNDEFINED = {"zero_target_count": "∅ target", "zero_reference_count": "∅ reference",
                   "empty_target": "empty target", "empty_reference": "empty reference", "empty_both": "both empty"}


# The same, in a column without bars (40-column splits).
TINY_UNDEFINED = {"zero_target_count": "∅ target", "zero_reference_count": "∅ ref.",
                  "empty_target": "empty", "empty_reference": "empty", "empty_both": "empty"}


class OpenSource(Message):
    """Ask the reader to open a source: a corpus passage, offset and digest."""

    def __init__(self, source):
        super().__init__()
        self.source = source


class Status(Message):
    """A one-line report for the status line."""

    def __init__(self, text):
        super().__init__()
        self.text = text


class VimTable(DataTable):
    """A row table that also moves the way the reader does."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("ctrl+d", "page_down", "Half page down", show=False),
        Binding("ctrl+u", "page_up", "Half page up", show=False),
    ]

    def __init__(self, **options):
        options.setdefault("cursor_type", "row")
        options.setdefault("cell_padding", 0)
        super().__init__(**options)


def right(value):
    return Text(value, justify="right")


def where(label):
    """A source's location for the gutter: its printed page, or a file offset."""
    if " | p. " in label:
        return "p." + label.rsplit(" | p. ", 1)[1]
    if label.startswith("text file, at character "):
        return "@" + label.removeprefix("text file, at character ")
    return label


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

    def compose(self):
        with Vertical(id="sort-dialog"):
            yield Static("Sort words · undefined values always last\n"
                         "Arrows choose · Enter applies · Escape cancels", id="sort-help")
            yield OptionList("Engine order (default)",
                             *(f"{words.SORT_COLUMNS[column]} · {'descending' if descending else 'ascending'}"
                               for column, descending in self.choices[1:]), id="sort-options")

    def on_mount(self):
        options = self.query_one(OptionList)
        options.highlighted = self.choices.index(self.current)
        options.focus()

    def on_option_list_option_selected(self, event):
        self.dismiss(self.choices[event.option_index])

    def action_cancel(self):
        self.dismiss(None)


class ResultView(Vertical):
    """What every study's view shares: a totals line, details, a saved status."""

    count = None
    saved = None

    def wide(self):
        return self.app.size.width >= WIDE

    def details_lines(self):
        return []

    def show_details(self, shown=None):
        box = self.query_one(".details")
        box.display = (not box.display) if shown is None else shown
        if not self.wide():
            box.set_class(box.display, "-open")

    def saved_line(self):
        return (f"Saved: {self.saved} (check with: sol essence check FILE)" if self.saved
                else "Not saved: this reader session has no workspace.")


class WordsView(ResultView):
    """Word frequencies or a comparison: words, a concordance, and where they occur."""

    BINDINGS = [
        Binding("slash", "filter", "Filter"),
        Binding("ctrl+f", "filter", "Filter", show=False),
        Binding("s", "sort", "Sort"),
        Binding("less_than_sign", "sort_context('left')", "Sort by left", show=False),
        Binding("greater_than_sign", "sort_context('right')", "Sort by right", show=False),
        Binding("i", "details", "Details"),
        Binding("f", "function_words", "Function words", show=False),
        Binding("e", "export('csv')", "Export CSV", show=False),
        Binding("E", "export('tsv')", "Export TSV", show=False),
        Binding("h", "pane(-1)", "Pane left", show=False),
        Binding("l", "pane(1)", "Pane right", show=False),
    ]

    word_sort = (None, False)
    word_filter = ""
    word_order = ()
    shown_sources = ()
    context_sort = None
    columns = "full"
    hide_function_words = False  # a session's display choice, off by default

    def compose(self):
        with Horizontal(classes="metrics-row"):
            yield Static("", id="result-metrics", markup=False)
            yield Static("", id="details-hint", markup=False)
        yield Input(placeholder="Filter words · Enter to the list · Esc clears", id="word-filter")
        yield Static("", id="sort-status", markup=False)
        with Horizontal(id="words-layout", classes="result-layout"):
            yield VimTable(id="frequencies")
            with Vertical(id="occurrences-pane"):
                yield Static("", id="sources-label", markup=False)
                yield VimTable(id="sources")
            with VerticalScroll(id="summary-box", classes="details"):
                yield Static("", id="summary", markup=False)

    def on_mount(self):
        self.query_one("#word-filter").display = False
        self.query_one("#word-filter").tooltip = ("Filter normalized word spellings; counts, denominators "
                                                  "and exports retain the full study.")

    # Showing a count -------------------------------------------------------
    def show(self, count, saved):
        new = count is not self.count
        self.count, self.saved = count, saved
        if new:
            self.word_sort, self.word_filter, self.context_sort = (None, False), "", None
            with self.prevent(Input.Changed):
                self.query_one("#word-filter", Input).value = ""
            self.query_one("#word-filter").display = False
            self.show_details(self.wide())
        self.rebuild()
        self.call_after_refresh(self.reflow)

    def rebuild(self, selected=None, source_row=0):
        """Draw the tables for the present width, keeping the chosen word and occurrence."""
        count = self.count
        wide = self.wide()
        self.set_class(wide, "-wide")
        if wide:
            self.query_one("#summary-box").display = True
        comparison = count.comparison is not None
        self.query_one("#result-metrics", Static).update(self.metrics())
        notes = len((count.comparison if comparison else count.study).get("warnings", []))
        self.query_one("#details-hint", Static).update(
            "" if wide else ("i details" + (f" ({notes})" if notes else "")))
        table = self.query_one("#frequencies", VimTable)
        ordered = words.row_order(count, *self.word_sort)
        hidden = self.hidden_words()
        matching = [index for index in ordered
                    if self.word_filter in count.study["frequencies"][index]["word"]
                    and count.study["frequencies"][index]["word"] not in hidden]
        self.word_order = tuple(matching[:words.ROW_LIMIT])
        with self.prevent(DataTable.RowHighlighted):
            self.fill_words(table)
        total = len(count.study["frequencies"])
        status = self.query_one("#sort-status", Static)
        parts = []
        if self.word_filter:
            parts.append(f"{len(self.word_order):,} of {len(matching):,} matching "
                         f"{'word' if len(matching) == 1 else 'words'}" if matching
                         else "No matching words · Esc clears the filter")
        elif len(self.word_order) < total:
            parts.append(f"{len(self.word_order):,} of {total:,} words")
        if hidden:
            parts.append(f"function words hidden ({self.app.function_words()['id']})")
        if self.word_sort[0] is not None:
            column, descending = self.word_sort
            parts.append(f"{words.SORT_COLUMNS[column]} · {'descending' if descending else 'ascending'}"
                         " · undefined last")
        status.update(" · ".join(parts))
        status.display = bool(parts)
        self.query_one("#summary", Static).update("\n".join(self.details_lines()))
        if selected is not None and selected in self.word_order:
            row = self.word_order.index(selected)
        else:
            row = 0
        with self.prevent(DataTable.RowHighlighted):
            if table.row_count:
                table.move_cursor(row=row, animate=False)
        self.show_sources(self.word_order[row] if self.word_order else None, source_row)

    def metrics(self):
        study = self.count.study
        target = study["target"]["summary"]
        line = f"target {target['token_count']:,} tokens"
        if self.count.reference is not None:
            line += f" · reference {study['reference']['summary']['token_count']:,} tokens"
        line += f" · {target['type_count']:,} distinct words"
        content = Text(line)
        # The following space stays in the bold run so SVG previews keep it.
        content.highlight_regex(r"\d[\d,]*(?:\s|$)", "bold")
        return content

    def details_lines(self):
        lines = words.summary(self.count)
        if self.word_filter:
            lines.append(f"Display filter: {self.query_one('#word-filter', Input).value!r}; "
                         f"{len(self.word_order):,} matching words shown. Counts and exports retain the full study.")
        if self.hidden_words():
            catalog = self.app.function_words()
            lines.append(f"Display: function words hidden by the declared list {catalog['id']} "
                         f"({len(catalog['words']):,} spellings). Counts, denominators, saved artifacts "
                         "and exports keep every word.")
        lines.append(self.saved_line())
        return lines

    def hidden_words(self):
        if not self.hide_function_words:
            return frozenset()
        catalog = self.app.function_words()
        return catalog["words"] if catalog else frozenset()

    def action_function_words(self):
        if self.app.function_words() is None:
            self.post_message(Status("This installation has no function-word list."))
            return
        self.hide_function_words = not self.hide_function_words
        if self.count is not None:
            self.rebuild(self.selected_word())

    def table_width(self, selector):
        """Cells available to a table: its pane, less one column of scrollbar.

        The window's width bounds an estimate of the pane; a laid-out table's
        own width can only narrow it (just after a resize, it is still the old one).
        """
        width = self.app.size.width
        if selector == "#frequencies":
            width = min(WORDS_PANE, width) if self.wide() else width
        elif self.wide():
            width = width - WORDS_PANE - DETAILS_PANE - 2
        estimate = width - 3
        laid_out = self.query_one(selector).size.width
        if laid_out:
            estimate = min(estimate, laid_out - 1)
        return max(10, estimate)

    def fill_words(self, table):
        count = self.count
        budget = self.table_width("#frequencies")
        table.clear(columns=True)
        rows = count.comparison["rows"] if count.comparison is not None else count.study["frequencies"]
        shown = [rows[index] for index in self.word_order]
        peak = max((max(row["target"]["rate_per_10000_tokens"] or 0,
                        (row["reference"] or {}).get("rate_per_10000_tokens") or 0) for row in shown),
                   default=0)
        longest = max((len(row["word"]) for row in shown), default=4)
        reference = count.reference is not None
        comparison = count.comparison is not None
        # What fits, in order of what goes first: bars, then rates, then the
        # log ratio's bar; counts always stay. The difference only fullscreen.
        sides_count = 2 if reference else 1
        difference = comparison and self.wide()
        word_width = max(4, min(longest + 1, 16))
        layouts = [(True, True), (True, False), (False, False)] if comparison else [(True, True), (False, False)]
        for show_rates, log_bar in layouts:
            fixed = sides_count * (6 + (8 if show_rates else 0)) + \
                ((16 if log_bar else 10) if comparison else 0) + (11 if difference else 0)
            if min(word_width, 8) + fixed <= budget:
                break
        word_width = max(4, min(word_width, budget - fixed))
        room = budget - word_width - fixed
        bars = max(0, min(16, room // sides_count - 1))
        if bars < 3:
            bars = 0
        self.log_bar = log_bar
        table.add_column("word", width=word_width)
        sides = [("target", "target")] + ([("reference", "reference")] if reference else [])
        for side, label in sides:
            table.add_column(right("n"), width=6)
            if show_rates:
                table.add_column(right("/10k"), width=8)
            if bars:
                table.add_column(" " + label, width=bars + 1)
        difference = comparison and self.wide()
        if difference:
            table.add_column(right("difference"), width=11)
        if comparison:
            table.add_column(" log₂ ratio" if log_bar else " log₂", width=16 if log_bar else 10)
        for index, row in zip(self.word_order, shown):
            cells = [row["word"][:word_width]]
            for side, _ in sides:
                cell = row[side]
                rate = cell["rate_per_10000_tokens"] if cell else None
                cells.append(right(f"{cell['count']:,} " if cell else ""))
                if show_rates:
                    cells.append(right("undefined " if cell and rate is None else f"{rate:.2f} " if rate is not None else ""))
                if bars:
                    style = "bold" if side == "target" else "dim"
                    cells.append(Text(" " + views.bar(rate or 0, peak, bars), style=style))
            if difference:
                value = row["rate_difference_per_10000_tokens"]
                cells.append(right(f"{value:+.2f} " if row["rate_difference_status"] == "defined" else "undefined "))
            if comparison:
                ratio = row["log2_rate_ratio"]
                status = row["log2_ratio_status"]
                if status == "defined" and log_bar:
                    left, right_bar = views.diverging(ratio)
                    cells.append(Text.assemble((left, "dim"), ("┊", "dim"), (right_bar, "bold"), f" {ratio:+.2f}"))
                elif status == "defined":
                    cells.append(Text(f" {ratio:+.2f}"))
                else:
                    reason = SHORT_UNDEFINED.get(status, "undefined")
                    cells.append(Text(("    " + reason) if log_bar else " " + TINY_UNDEFINED.get(status, reason),
                                      style="dim"))
            table.add_row(*cells, key=str(index))
        table.border_title = None

    # The concordance ----------------------------------------------------------
    def show_sources(self, index, source_row=0):
        table = self.query_one("#sources", VimTable)
        label = self.query_one("#sources-label", Static)
        table.clear(columns=True)
        if index is None:
            self.shown_sources = ()
            label.update("No word selected" if not self.word_filter else "No matching words")
            return
        row = self.count.study["frequencies"][index]
        found = words.sources(self.count, index)
        if self.context_sort is not None:
            found = sorted(found, key=lambda item: views.context_key(item["context"], self.context_sort))
        self.shown_sources = tuple(found)
        total = sum(row[side]["count"] for side in ("target", "reference") if row[side] is not None)
        budget = self.table_width("#sources")
        # The node column fits the word, but never more than a quarter of the line.
        node = min(max((cell_len(item["context"]["word"]) for item in found if item["context"]),
                       default=cell_len(row["word"])) + 2, max(6, budget // 4))
        gutter = 9
        context = max(8, budget - 1 - node - gutter)
        left_width = context * 9 // 20
        right_width = context - left_width
        table.add_column(" ", width=1)
        table.add_column(right("left context"), width=left_width)
        table.add_column("", width=node)
        table.add_column("right context", width=right_width)
        table.add_column(right("where"), width=gutter)
        for item in found:
            left, word, right_text = views.kwic(item["context"], left_width - 1, right_width - 1)
            glued = right_text[:1] in tuple(",;:.!?)…") and not item["context"]["right"][:1].isspace() \
                if item["context"] else False
            side = Text("▌", style="bold" if item["side"] == "target" else "dim")
            shown = Text(" " + word + ("" if glued else " "), style="bold reverse")
            shown.truncate(node, overflow="ellipsis")
            table.add_row(side, Text(left + " "), shown,
                          Text(right_text), right(where(item["label"]) + " "))
        positions = [item["position"] for item in found if item["side"] == "target" and item.get("position") is not None]
        sides = [f"{row[side]['count']:,} in {side}" for side in ("target", "reference") if row[side] is not None]
        head = f" {row['word']} · " + " · ".join(sides) + " "
        order = {"left": " · sorted by left context", "right": " · sorted by right context"}.get(self.context_sort, "")
        strip_width = max(0, min(30, budget - len(head) - len(order) - 10))
        strip = views.dispersion(positions, strip_width) if positions and strip_width >= 6 else ""
        listing = "" if len(found) == total else f" · listing {len(found):,} of {total:,}"
        title = Text.assemble((head, "bold"), (listing + order, "dim"))
        if strip:
            title.append("  ")
            title.append(strip, style="bold")
            title.append(" where", style="dim")
        label.update(title)
        label.tooltip = "Occurrences · Enter opens in the reader · < and > sort by context · Escape returns to words"
        if table.row_count:
            table.move_cursor(row=min(source_row, table.row_count - 1), animate=False)

    # Events -----------------------------------------------------------------------
    def on_data_table_row_highlighted(self, event):
        if event.data_table.id == "frequencies" and self.count is not None:
            event.stop()
            self.show_sources(int(event.row_key.value))

    def on_data_table_row_selected(self, event):
        event.stop()
        if event.data_table.id == "frequencies":
            self.query_one("#sources").focus()
            return
        if not 0 <= event.cursor_row < len(self.shown_sources):
            return
        source = self.shown_sources[event.cursor_row]["open"]
        if source is None:
            self.post_message(Status("A text file's words cannot be opened in the reader."))
        else:
            self.post_message(OpenSource(source))

    def on_input_changed(self, event):
        if event.input.id != "word-filter" or self.count is None:
            return
        event.stop()
        if event.value != event.input.value:
            return  # A new result may already have cleared an old queued edit.
        query = normalized(event.value)
        if query != self.word_filter:
            self.word_filter = query
            self.rebuild()

    def on_input_submitted(self, event):
        if event.input.id == "word-filter":
            event.stop()
            self.query_one("#frequencies").focus()

    def on_key(self, event):
        field = self.query_one("#word-filter", Input)
        if event.key != "escape":
            return
        if self.app.focused is field:
            if field.value:
                field.value = ""
            else:
                field.display = False
                self.query_one("#frequencies").focus()
        elif self.app.focused is self.query_one("#sources"):
            self.query_one("#frequencies").focus()
        elif self.app.focused is self.query_one("#summary-box"):
            self.query_one("#frequencies").focus()
        elif field.value:
            field.value = ""
            field.display = False
        else:
            return
        event.stop()
        event.prevent_default()

    # Actions ------------------------------------------------------------------------
    def action_filter(self):
        field = self.query_one("#word-filter", Input)
        field.display = True
        field.focus()

    def action_sort(self):
        if self.count is not None and self.count.comparison is not None:
            self.app.push_screen(WordSort(self.word_sort), self.sort_words)
        else:
            self.post_message(Status("Sorting needs a comparison: choose a reference with r."))

    def sort_words(self, choice):
        if choice is not None:
            self.word_sort = choice
            self.rebuild(self.selected_word())

    def action_sort_context(self, side):
        self.context_sort = None if self.context_sort == side else side
        self.show_sources(self.selected_word())
        self.query_one("#sources").focus()

    def action_details(self):
        if self.wide():
            self.query_one("#summary-box").focus()
            return
        self.show_details()
        box = self.query_one("#summary-box")
        (box if box.display else self.query_one("#frequencies")).focus()

    def action_pane(self, step):
        panes = [self.query_one(selector) for selector in ("#frequencies", "#sources", "#summary-box")
                 if self.query_one(selector).display]
        focused = self.app.focused
        position = panes.index(focused) if focused in panes else 0
        panes[(position + step) % len(panes)].focus()

    def action_export(self, table_format):
        self.app.export(table_format)

    def selected_word(self):
        table = self.query_one("#frequencies", VimTable)
        row = table.cursor_row
        return self.word_order[row] if 0 <= row < len(self.word_order) else None

    def reflow(self):
        if self.count is None:
            return
        source_row = self.query_one("#sources", VimTable).cursor_row
        focused = self.app.focused
        self.rebuild(self.selected_word(), source_row)
        if focused is not None and focused.display:
            focused.focus()


def normalized(value):
    import unicodedata
    return unicodedata.normalize("NFC", value.strip()).casefold().replace("’", "'")


class SentencesView(ResultView):
    """Sentence lengths: the distribution first, then the longest sentences."""

    BINDINGS = [Binding("i", "details", "Details")]

    def compose(self):
        with Horizontal(classes="metrics-row"):
            yield Static("", id="sentence-metrics", markup=False)
            yield Static("", classes="details-hint", markup=False)
        with Horizontal(classes="result-layout"):
            with VerticalScroll(id="distribution"):
                yield Static("", id="histogram", markup=False)
            with Vertical(id="longest-pane"):
                yield Static("", id="longest-label", markup=False)
                yield VimTable(id="longest")
            with VerticalScroll(id="sentence-details", classes="details"):
                yield Static("", id="sentence-summary", markup=False)

    def show(self, count, saved):
        new = count is not self.count
        self.count, self.saved = count, saved
        if new:
            self.show_details(self.wide())
        self.rebuild()
        self.call_after_refresh(self.reflow)

    def rebuild(self):
        study = self.count.study
        wide = self.wide()
        self.set_class(wide, "-wide")
        if wide:
            self.query_one("#sentence-details").display = True
        totals = study["summary"]
        mean = "—" if totals["mean"] is None else f"{totals['mean']:.1f}"
        line = Text(f"{views.plural(totals['sentences'], 'sentence')} · {views.plural(totals['tokens'], 'word')} · mean {mean}")
        line.highlight_regex(r"\d[\d,.]*(?:\s|$)", "bold")
        self.query_one("#sentence-metrics", Static).update(line)
        self.query_one(".details-hint", Static).update("" if wide else "i details")
        width = self.app.size.width
        histogram_width = (width - DETAILS_PANE - 2) // 2 if wide else width
        self.query_one("#histogram", Static).update(self.histogram(max(20, histogram_width - 4)))
        table = self.query_one("#longest", VimTable)
        table.clear(columns=True)
        budget = (width - DETAILS_PANE - histogram_width - 4) if wide else width - 3
        if table.size.width:
            budget = min(budget, table.size.width - 1)
        gutter = 9
        table.add_column(right("words"), width=6)
        table.add_column(" beginning", width=max(8, budget - 6 - gutter))
        table.add_column(right("where"), width=gutter)
        for tokens, beginning, label in sentences.rows(self.count):
            limit = max(8, budget - 6 - gutter - 2)
            shown = beginning if len(beginning) <= limit else beginning[:limit - 1].rstrip() + "…"
            table.add_row(right(tokens + " "), Text(" " + shown), right(where(label.replace("\n", " ")) + " "))
        self.query_one("#longest-label", Static).update(
            Text.assemble(("longest sentences", "bold"), (" · Enter opens one at its first letter", "dim")))
        self.query_one("#sentence-summary", Static).update("\n".join(self.details_lines()))

    def histogram(self, width):
        study = self.count.study
        totals = study["summary"]
        if not totals["sentences"]:
            return Text("No sentences to measure.", style="dim")
        bins = views.histogram(study["histogram"], max(6, width - 16))
        text = Text()
        text.append("words per sentence", style="dim")
        text.append(f"   median {totals['median']} · middle 80% {totals['p10']}–{totals['p90']} · longest {totals['max']}\n",
                    style="dim")
        for label, bar, number in bins:
            text.append(f"{label:>8} ")
            text.append(bar, style="bold")
            text.append(f" {number:>5,}\n")
        file = study["input"]["provider"] == "file"
        text.append("\nby place " + ("among the file's sentences" if file else "in the paragraph") + "\n", style="dim")
        peak = max((study["by_position"][key]["mean"] or 0 for key, _ in sentences.POSITIONS), default=0)
        for key, label in (sentences.FILE_POSITIONS if file else sentences.POSITIONS):
            part = study["by_position"][key]
            mean = "—" if part["mean"] is None else f"{part['mean']:.1f}"
            text.append(f"{label.split()[0].lower():>8} ")
            text.append(views.bar(part["mean"] or 0, peak, max(6, (width - 16) // 2)), style="dim")
            text.append(f" mean {mean} · {views.plural(part['sentences'], 'sentence')}\n")
        return text

    def details_lines(self):
        # The distribution is drawn beside it; the details keep the rest as text.
        lines = [line for line in sentences.summary(self.count) if "█" not in line]
        if self.count.study["longest"]:
            lines.append("Enter on one of the longest sentences opens it in the reader (Alt-Left there returns).")
        lines.append(self.saved_line())
        return lines

    def on_data_table_row_selected(self, event):
        event.stop()
        if not 0 <= event.cursor_row < len(self.count.study["longest"][:sentences.ROW_LIMIT]):
            return
        source = sentences.source(self.count, event.cursor_row)
        if source is None:
            self.post_message(Status("A text file's sentences cannot be opened in the reader."))
        else:
            self.post_message(OpenSource(source))

    def on_key(self, event):
        if event.key == "escape" and self.app.focused is self.query_one("#sentence-details"):
            self.query_one("#longest").focus()
            event.stop()

    def action_details(self):
        if self.wide():
            self.query_one("#sentence-details").focus()
            return
        self.show_details()
        box = self.query_one("#sentence-details")
        (box if box.display else self.query_one("#longest")).focus()

    def reflow(self):
        if self.count is None:
            return
        table = self.query_one("#longest", VimTable)
        row, focused = table.cursor_row, self.app.focused
        self.rebuild()
        if table.row_count:
            table.move_cursor(row=min(row, table.row_count - 1), animate=False)
        if focused is not None and focused.display:
            focused.focus()


class TfidfView(ResultView):
    """TF-IDF: each passage's top terms, then the overall mean weights with bars."""

    BINDINGS = [Binding("i", "details", "Details"), Binding("h", "pane(-1)", "Pane left", show=False),
                Binding("l", "pane(1)", "Pane right", show=False)]

    def compose(self):
        with Horizontal(classes="metrics-row"):
            yield Static("", id="tfidf-metrics", markup=False)
            yield Static("", classes="details-hint", markup=False)
        with Horizontal(classes="result-layout"):
            with Vertical(id="passages-pane"):
                yield Static("", id="passages-label", markup=False)
                yield VimTable(id="passages")
            with Vertical(id="overall-pane"):
                yield Static("", id="overall-label", markup=False)
                yield VimTable(id="overall")
            with VerticalScroll(id="tfidf-details", classes="details"):
                yield Static("", id="tfidf-summary", markup=False)

    def show(self, count, saved):
        new = count is not self.count
        self.count, self.saved = count, saved
        if new:
            self.show_details(self.wide())
        self.rebuild()

    def rebuild(self):
        study = self.count.study
        wide = self.wide()
        self.set_class(wide, "-wide")
        if wide:
            self.query_one("#tfidf-details").display = True
        totals = study["word_study"]["target"]["summary"]
        line = Text(f"{totals['token_count']:,} tokens · {views.plural(totals['input_count'], 'input')} · "
                    f"top {study['top_n']} terms each")
        line.highlight_regex(r"\d[\d,]*(?:\s|$)", "bold")
        self.query_one("#tfidf-metrics", Static).update(line)
        self.query_one(".details-hint", Static).update("" if wide else "i details")
        width = self.app.size.width
        overall_width = 40 if wide else width - 3
        passages_width = (width - DETAILS_PANE - overall_width - 6) if wide else width - 3
        table = self.query_one("#passages", VimTable)
        if table.size.width:
            passages_width = min(passages_width, table.size.width - 1)
        if self.query_one("#overall").size.width:
            overall_width = min(overall_width, self.query_one("#overall").size.width - 1)
        table.clear(columns=True)
        label_width = min(30, max(12, passages_width // 3))
        table.add_column(" passage", width=label_width)
        table.add_column(" top terms · weight", width=max(10, passages_width - label_width))
        for label, terms in tfidf.rows(self.count):
            table.add_row(Text(" " + label.replace("\n", " · "), overflow="fold"),
                          Text(" " + terms, overflow="fold"), height=None)
        self.query_one("#passages-label", Static).update(
            Text.assemble(("terms by passage", "bold"), (" · Enter opens a passage", "dim")))
        overall = self.query_one("#overall", VimTable)
        overall.clear(columns=True)
        rows = study["overall"]
        peak = max((row["score"] for row in rows), default=0)
        bar_width = max(0, min(30, overall_width - 16 - 9))
        term_width = overall_width - 9 - bar_width
        overall.add_column(" term", width=min(term_width, 24))
        overall.add_column(right("weight"), width=9)
        if bar_width >= 3:
            overall.add_column("", width=bar_width)
        for row in rows:
            cells = [Text(" " + row["word"], overflow="fold"), right(f"{row['score']:.4f} ")]
            if bar_width >= 3:
                cells.append(Text(views.bar(row["score"], peak, bar_width), style="bold"))
            overall.add_row(*cells, height=None)
        self.query_one("#overall-label", Static).update(
            Text.assemble(("overall", "bold"), (" · mean passage weights", "dim")))
        self.query_one("#tfidf-summary", Static).update("\n".join(self.details_lines()))

    def details_lines(self):
        return [*tfidf.summary(self.count), self.saved_line()]

    def on_data_table_row_selected(self, event):
        event.stop()
        if event.data_table.id != "passages":
            return
        source = tfidf.source(self.count, event.cursor_row)
        if source is None:
            self.post_message(Status("A text file cannot be opened in the reader."))
        else:
            self.post_message(OpenSource(source))

    def on_key(self, event):
        if event.key == "escape" and self.app.focused in (self.query_one("#tfidf-details"), self.query_one("#overall")):
            self.query_one("#passages").focus()
            event.stop()

    def action_details(self):
        if self.wide():
            self.query_one("#tfidf-details").focus()
            return
        self.show_details()
        box = self.query_one("#tfidf-details")
        (box if box.display else self.query_one("#passages")).focus()

    def action_pane(self, step):
        panes = [self.query_one(selector) for selector in ("#passages", "#overall", "#tfidf-details")
                 if self.query_one(selector).display]
        focused = self.app.focused
        position = panes.index(focused) if focused in panes else 0
        panes[(position + step) % len(panes)].focus()

    def reflow(self):
        if self.count is None:
            return
        table = self.query_one("#passages", VimTable)
        row, focused = table.cursor_row, self.app.focused
        self.rebuild()
        if table.row_count:
            table.move_cursor(row=min(row, table.row_count - 1), animate=False)
        if focused is not None and focused.display:
            focused.focus()
