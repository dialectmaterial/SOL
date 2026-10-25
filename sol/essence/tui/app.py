"""ESSENCE interface: one workspace where a study's result is home.

Neovim owns the outer layout (beside the reader or fullscreen, Alt-F, and
Alt-R back to the reader); this app owns only what is inside its window.
A one-line header names the study and the reader's passage; below it the
result, the study menu (`r`) and a status line. The Encyclopedia and Methods
are reference, opened over the study (`K`, `M`, or `:`). Leaving saves which
view was open and for which passage, nothing else.
"""
from __future__ import annotations

import base64
import json

from rich.text import Text
from textual import work
from textual.app import App
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Provider
from textual.containers import Vertical, VerticalScroll
from textual.theme import Theme
from textual.widgets import ContentSwitcher, Footer, Input, Markdown, Static

from sol.essence.encyclopedia import load_catalog
from sol.essence.methods import load_methods, method_markdown
from sol.essence.tui import sentences, tfidf, words
from sol.essence.tui.context import load_state, save_state
from sol.essence.tui.menu import STUDIES, SCOPES, StudyMenu
from sol.essence.tui.reference import METHOD_STUDIES, ReferenceScreen
from sol.essence.tui.results import OpenSource, SentencesView, Status, TfidfView, WordsView, WIDE, focus_now
from sol.presentation.theme import BACKGROUNDS, DEFAULT_READER_THEME, READER_THEMES, reader_palette

TEXTUAL_THEMES = {name: f"sol-{name}" for name in READER_THEMES if name != "terminal"} | {"terminal": "ansi-dark"}


def blend(first, second, share):
    """The #rrggbb color `share` of the way from `first` to `second`."""
    one, two = (tuple(int(color[index:index + 2], 16) for index in (1, 3, 5)) for color in (first, second))
    return "#" + "".join(f"{round(a + (b - a) * share):02x}" for a, b in zip(one, two))


def reader_theme(name):
    """ESSENCE in the reader's own colors: its page, ink, headings, rules and selection.

    Terminal has no palette; Textual's ANSI theme inherits the terminal's colors as the reader does.
    """
    p = reader_palette(name)
    return Theme(
        name=TEXTUAL_THEMES[name], dark=BACKGROUNDS[name] == "dark",
        foreground=p["text"], background=p["page"], surface=p["panel"], panel=p["selection"],
        primary=p["heading"], secondary=p["muted"], accent=p["heading"],
        warning=p["warning"], error=p["warning"], success=p["heading"],
        variables={
            "text-muted": p["muted"], "foreground-muted": p["muted"],
            "border": p["heading"], "border-blurred": p["border"],
            "block-cursor-foreground": p["text"], "block-cursor-background": p["selection"],
            "block-cursor-text-style": "bold",
            # Halfway to the selection: visible even where the panel is the page (Latte).
            "block-cursor-blurred-foreground": p["text"],
            "block-cursor-blurred-background": blend(p["page"], p["selection"], 0.5),
            "input-cursor-foreground": p["page"], "input-cursor-background": p["text"],
            "input-selection-background": p["selection"],
            "footer-background": p["page"], "footer-foreground": p["muted"],
            "footer-key-foreground": p["heading"], "footer-description-foreground": p["muted"],
            "scrollbar": p["border"], "scrollbar-hover": p["muted"], "scrollbar-active": p["heading"],
            "scrollbar-background": p["page"], "scrollbar-background-hover": p["page"],
            "scrollbar-background-active": p["page"], "scrollbar-corner-color": p["page"],
            # Headings and menu choices are not links: bold, not underlined; links keep their color.
            "link-color": p["heading"], "link-color-hover": p["text"], "link-background-hover": p["selection"],
            "link-style": "none", "link-style-hover": "underline",
            "button-foreground": p["text"], "button-color-foreground": p["page"],
            **{f"markdown-h{level}-{part}": value for level in range(1, 7)
               for part, value in (("color", p["heading"]), ("background", "transparent"),
                                   ("text-style", "bold"))},
        })


# Views a leaving session can return to; earlier screens map onto them.
VIEWS = {"workspace": "workspace", "experiment": "workspace", "results": "workspace",
         "encyclopedia": "encyclopedia", "methods": "methods"}
# The method each study's `K` opens.
STUDY_METHODS = {"words": "words", "sentences": "sentences", "tfidf": "tfidf"}
INTRO = ("Choose a study below: its result appears here, with every measurement's passages one Enter away.\n"
         "K explains the method · M opens the Encyclopedia and Methods · ? lists every key · "
         "Alt-F fullscreen ⇄ beside · Alt-R back to the reader")


class EssenceCommands(Provider):
    """The command palette (`:`): ESSENCE's own actions and every catalog entry."""

    def commands(self):
        app = self.app
        found = [("Choose a study", app.action_menu, "Study, target and reference (r)"),
                 ("Encyclopedia", lambda: app.action_reference("encyclopedia"), "Methods' history and sources (M)"),
                 ("Methods", lambda: app.action_reference("methods"), "What each study computes"),
                 ("Leave ESSENCE", app.action_leave, "Save the open view and close (q)")]
        if isinstance(app.last_count, words.Count) and app.last_count.reference is not None:
            found += [("Export CSV", lambda: app.export("csv"), "The complete comparison table (e)"),
                      ("Export TSV", lambda: app.export("tsv"), "The complete comparison table (E)")]
        for item in app.methods["entries"]:
            found.append((f"Method: {item['title']}",
                          lambda identifier=item["id"]: app.action_reference("methods", identifier), item["summary"]))
        for index, item in enumerate(app.catalog["entries"]):
            found.append((f"Encyclopedia: {item['title']}",
                          lambda position=index: app.action_reference("encyclopedia", entry=position), None))
        return found

    async def discover(self):
        for title, command, help_text in self.commands()[:6]:
            yield DiscoveryHit(title, command, help=help_text)

    async def search(self, query):
        matcher = self.matcher(query)
        for title, command, help_text in self.commands():
            score = matcher.match(title)
            if score > 0:
                yield Hit(score, matcher.highlight(title), command, help=help_text)


class EssenceApp(App):
    """One investigation, shown in whatever space Neovim gives it."""

    TITLE = "SOL ESSENCE"
    COMMANDS = {EssenceCommands}
    COMMAND_PALETTE_BINDING = "colon"
    CSS = """
    Screen { background: $background; }
    #header { height: 1; padding: 0 1; text-wrap: nowrap; text-overflow: ellipsis; }
    #workspace { height: 1fr; }
    #intro { height: auto; padding: 1 2; color: $text-muted; }
    #results { height: 1fr; }
    #results.-empty { height: auto; }
    ResultView { height: 1fr; padding: 0 1; }
    .metrics-row { height: 1; }
    #result-metrics, #sentence-metrics, #tfidf-metrics { width: 1fr; text-wrap: nowrap; text-overflow: ellipsis; }
    #details-hint, .details-hint { width: auto; padding-left: 2; color: $text-muted; }
    #word-filter { height: 1; border: none; padding: 0 1; background: $surface; }
    #sort-status { height: 1; color: $text-muted; text-wrap: nowrap; text-overflow: ellipsis; }
    .result-layout { height: 1fr; layout: vertical; }
    ResultView.-wide .result-layout { layout: horizontal; }
    VimTable { background: $background; scrollbar-size-vertical: 1; }
    VimTable > .datatable--header { background: $background; color: $text-muted; text-style: bold; }
    VimTable > .datatable--cursor { background: $block-cursor-blurred-background; color: $foreground; }
    VimTable:focus > .datatable--cursor { background: $block-cursor-background; color: $block-cursor-foreground;
        text-style: bold; }
    #frequencies { height: 1fr; min-height: 4; }
    #occurrences-pane { height: 1fr; min-height: 5; }
    #sources-label, #longest-label, #passages-label, #overall-label {
        height: 1; color: $text-muted; text-wrap: nowrap; text-overflow: ellipsis;
        border-top: solid $border-blurred; height: 2; }
    #occurrences-pane:focus-within #sources-label, #longest-pane:focus-within #longest-label,
    #passages-pane:focus-within #passages-label, #overall-pane:focus-within #overall-label {
        color: $accent; border-top: solid $accent; }
    #sources { height: 1fr; }
    .details { display: none; height: auto; max-height: 45%; padding: 0 1;
               border-top: solid $border-blurred; color: $text-muted; }
    .details:focus { border-top: solid $accent; }
    ResultView.-wide .details { display: block; height: 1fr; max-height: 100%; width: 40;
                                border-top: none; border-left: vkey $border-blurred; }
    ResultView.-wide #frequencies { width: 86; height: 1fr; }
    ResultView.-wide #occurrences-pane { width: 1fr; height: 1fr; border-left: vkey $border-blurred; padding-left: 1; }
    ResultView.-wide #sources-label { border-top: none; height: 1; }
    #distribution { height: auto; max-height: 50%; }
    ResultView.-wide #distribution { width: 1fr; height: 1fr; max-height: 100%; }
    #longest-pane { height: 1fr; }
    ResultView.-wide #longest-pane { width: 1fr; border-left: vkey $border-blurred; padding-left: 1; }
    #longest { height: 1fr; }
    #passages-pane { height: 1fr; }
    #overall-pane { height: 1fr; max-height: 40%; }
    ResultView.-wide #overall-pane { width: 42; max-height: 100%; border-left: vkey $border-blurred; padding-left: 1; }
    #passages, #overall { height: 1fr; }
    StudyMenu { height: auto; max-height: 100%; overflow-y: auto; padding: 0 1;
                border-top: solid $border-blurred; background: $background; }
    Screen.-short #intro { display: none; }
    #primer { height: 1fr; padding: 0 1; border-top: solid $border-blurred; scrollbar-size-vertical: 1; }
    #primer Markdown { padding: 0 1; color: $text-muted; }
    StudyMenu:focus-within { border-top: solid $accent; }
    #menu-choices { height: auto; }
    .menu-field { height: 1; }
    .menu-field Label { width: auto; color: $text-muted; }
    .menu-field Input { height: 1; border: none; padding: 0 1; background: $surface; width: 1fr; }
    #menu-summary { height: auto; margin-top: 1; }
    #status { height: auto; color: $warning; }
    #result-status { height: auto; max-height: 2; padding: 0 1; color: $text-muted; }
    Footer { background: $footer-background; }
    /* Reference screen: the catalogs, as before. */
    #reference-header { height: 1; padding: 0 1; }
    #catalogs, ContentSwitcher { height: 1fr; }
    ContentTabs { background: $background; }
    Tab { color: $text-muted; padding: 0 2; }
    Tab.-active { color: $accent; text-style: bold; }
    TabPane { padding: 0 1; }
    .browser-tools { height: 1; margin-bottom: 1; }
    .browser-search { width: 1fr; height: 1; border: none; padding: 0 1; background: $surface; }
    .browser-search:focus { border: none; background: $panel; }
    .browser-count { width: auto; padding-left: 1; color: $text-muted; }
    .browser-layout { height: 1fr; }
    .browser-list, .browser-detail { border: round $border-blurred; background: $background;
        border-title-color: $text-muted; border-title-style: bold; }
    .browser-list:focus, .browser-detail:focus { border: round $accent; border-title-color: $accent; }
    .browser-list { width: 32; height: 1fr; padding: 0 1; margin-right: 1; }
    .browser-detail { width: 1fr; height: 1fr; padding: 0 1; }
    #method-actions { height: 1; margin-top: 1; }
    #method-actions Button { height: 1; border: none; min-width: 20; }
    #method-availability { width: 1fr; color: $text-muted; }
    OptionList { background: $background; }
    OptionList > .option-list--option { padding: 0 1; }
    OptionList > .option-list--option-highlighted { background: $block-cursor-blurred-background; color: $foreground;
        text-style: bold; }
    OptionList:focus > .option-list--option-highlighted { background: $block-cursor-background;
        color: $block-cursor-foreground; }
    Markdown { padding: 0 1; }
    MarkdownH2 { margin-top: 0; }
    #genealogy-map { height: auto; border: none; background: transparent; padding: 0 1; }
    Screen.-compact .browser-layout { layout: vertical; }
    Screen.-compact .browser-list { width: 1fr; height: auto; min-height: 4; max-height: 40%; margin: 0 0 1 0; }
    Screen.-compact .browser-detail { width: 1fr; }
    """
    # The private terminal sequence that asks the reader to open a source; the
    # reader checks it and navigates only through its own guarded actions.
    SOURCE_SEQUENCE = "\x1b]5379;sol-essence;{}\x07"
    BINDINGS = [
        Binding("r", "menu", "Study"),
        Binding("K", "method", "Method"),
        Binding("M", "reference('encyclopedia')", "Encyclopedia"),
        Binding("R", "rerun", "Rerun", show=False),
        Binding("question_mark", "keys", "Keys"),
        # While counting, Escape cancels before any field or view can take it.
        Binding("escape", "cancel_count", "Cancel", show=False, priority=True),
        Binding("q", "leave", "Leave"),
        # Priority: the reader sends Ctrl-Q when it quits, whatever has focus.
        Binding("ctrl+q", "leave", "Leave ESSENCE", show=False, priority=True),
    ]

    count_serial = 0
    last_count = None
    last_saved = None
    last_run = None
    counting = False
    exporting = False

    def __init__(self, context, theme=DEFAULT_READER_THEME, theme_file=None, position_file=None):
        super().__init__()
        for name in READER_THEMES:
            if name != "terminal":
                self.register_theme(reader_theme(name))
        self.theme = TEXTUAL_THEMES[theme]
        self.theme_file = theme_file
        self.position_file = position_file
        self.position_seen = None
        self.catalog = load_catalog()
        self.methods = load_methods()
        self.context = context
        self.state_file = context["state_file"]
        self.state = load_state(self.state_file) if self.state_file else {}
        self.reading_moved = False
        self._function_words = None

    def get_system_commands(self, screen):
        # Theme and quit commands would bypass the reader's theme and ESSENCE's
        # own leaving; the palette offers only ESSENCE's commands.
        return iter(())

    def compose(self):
        yield Static("", id="header")
        with Vertical(id="workspace"):
            yield Static(INTRO, id="intro")
            with ContentSwitcher(id="results", initial=None):
                yield WordsView(id="words-view")
                yield SentencesView(id="sentences-view")
                yield TfidfView(id="tfidf-view")
            yield StudyMenu(id="menu")
            # Until the first result, the chosen study's method fills the space below the menu.
            with VerticalScroll(id="primer"):
                yield Markdown("", id="primer-method")
        yield Static("", id="result-status")
        yield Footer(compact=True)

    def on_mount(self):
        self.update_layout()
        self.query_one("#results").display = False
        self.update_header()
        self.theme_changed_signal.subscribe(self, self.restyle_open_screens)
        if self.theme_file:
            # A stat-sized read twice a second; T in the reader shows here within half a second.
            self.set_interval(0.5, self.follow_reader_theme)
        if self.position_file:
            self.set_interval(0.5, self.follow_reader_position)
        focus_now(self.query_one("#menu"))
        view = VIEWS.get(self.state.get("screen"), "workspace")
        if view != "workspace":
            self.action_reference(view)

    # The header ---------------------------------------------------------------------
    def title_style(self):
        """ESSENCE's name in the theme's heading color; Terminal's ANSI names become Rich's."""
        return "bold " + self.theme_variables["primary"].removeprefix("ansi_")

    def update_header(self):
        header = Text()
        header.append("ESSENCE", style=self.title_style())
        menu = self.query_one("#menu", StudyMenu)
        if self.last_run is not None:
            study, target, reference = self.last_run[:3]
            header.append(f"  {STUDIES[study]}", style="bold")
            header.append(f" · {SCOPES[target].removeprefix('the ')}")
            if study == "words" and reference != "none":
                header.append(f" ⇄ {SCOPES[reference].removeprefix('the ')}")
        else:
            header.append(f"  {STUDIES[menu.study]}", style="bold")
        header.append("   ")
        header.append(self.context["label"], style="dim")
        if self.reading_moved:
            header.append("  ↻ reading moved · R reruns", style="bold")
        self.query_one("#header", Static).update(header)

    def on_study_menu_changed(self, event):
        self.update_header()
        primer = self.query_one("#primer-method", Markdown)
        if self.last_count is None and self.methods is not None:
            menu = self.query_one("#menu", StudyMenu)
            method = "word-comparison" if menu.study == "words" and menu.reference != "none" else STUDY_METHODS[menu.study]
            entry = next(item for item in self.methods["entries"] if item["id"] == method)
            text = method_markdown(dict(entry, encyclopedia=None))
            if text != getattr(primer, "shown", None):
                primer.shown = text
                primer.update(text + "\n\nK opens this method in full · M the Encyclopedia")

    # Study menu and runs ------------------------------------------------------------
    def action_menu(self):
        menu = self.query_one("#menu", StudyMenu)
        menu.display = True
        focus_now(menu)

    def on_study_menu_close(self, event):
        if self.counting:
            self.cancel_count()
        elif self.last_count is not None:
            self.query_one("#menu").display = False
            self.focus_result()

    def on_study_menu_run(self, event):
        menu = self.query_one("#menu", StudyMenu)
        status = menu.query_one("#status", Static)
        top_n = 20
        if menu.study == "tfidf":
            value = menu.query_one("#top-n", Input).value.strip()
            try:
                top_n = int(value) if value.isascii() and value.isdecimal() else 0
            except ValueError:
                top_n = 0  # Also refuse values beyond Python's integer-string limit.
            if not 1 <= top_n <= 1000:
                status.update("Not counted: top_n must be an integer from 1 to 1,000.")
                focus_now(menu.query_one("#top-n", Input))
                return
        self.run_study(menu.study, menu.target, menu.reference, menu.query_one("#target-file", Input).value,
                       menu.query_one("#reference-file", Input).value, top_n)

    def run_study(self, study, target, reference, target_file, reference_file, top_n):
        """Count one complete request; `R` repeats exactly this, with the reader's present position."""
        menu = self.query_one("#menu", StudyMenu)
        status = menu.query_one("#status", Static)
        # Read the choices here, on the interface thread; each count has a
        # number, and only the latest one may save or show anything.
        self.count_serial += 1
        self.counting = True
        self.pending_run = (study, target, reference, target_file, reference_file, top_n)
        status.update("Counting… Esc cancels")
        if not menu.display:  # A rerun from the result: say so where it shows.
            self.query_one("#result-status", Static).update("Counting… Esc cancels")
        self.count_words(self.count_serial, target, reference, target_file, reference_file, study, top_n)

    def action_rerun(self):
        if self.last_run is not None and not self.counting:
            self.reading_moved = False
            self.update_header()
            self.run_study(*self.last_run)

    def cancel_count(self):
        # The engine cannot be interrupted midway: the count finishes in
        # the background, and its result is discarded like a replaced one.
        self.count_serial += 1
        self.counting = False
        self.query_one("#menu").query_one("#status", Static).update("Cancelled; nothing was saved.")
        if not self.query_one("#menu").display:
            self.query_one("#result-status", Static).update("Cancelled; nothing was saved.")

    @work(thread=True, exclusive=True)
    def count_words(self, serial, target, reference, target_file, reference_file, study="words", top_n=20):
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

    def finish_count(self, serial, outcome):
        # A replaced or abandoned count saves nothing and shows nothing.
        if serial != self.count_serial:
            return
        self.counting = False
        status = self.query_one("#menu").query_one("#status", Static)
        if isinstance(outcome, Exception):
            status.update(f"Not counted: {outcome}")
            self.query_one("#result-status", Static).update("")
            self.action_menu()  # The choices that failed, with the reason, ready to change.
            return
        status.update("")
        try:
            module = (tfidf if isinstance(outcome, tfidf.TfidfCount) else
                      sentences if isinstance(outcome, sentences.SentenceCount) else words)
            saved = module.save(outcome) if self.state_file else None
        except (words.EngineMissing, ValueError, OSError) as error:
            self.query_one("#result-status", Static).update(f"Counted, but not saved: {error}")
            saved = None
        else:
            self.query_one("#result-status", Static).update("")
        self.last_run = self.pending_run
        self.show_result(outcome, saved)

    def show_result(self, count, saved):
        self.last_count, self.last_saved = count, saved
        view = self.result_view(count)
        switcher = self.query_one("#results", ContentSwitcher)
        switcher.display = True
        self.query_one("#intro").display = False
        self.query_one("#primer").display = False
        switcher.current = view.id
        view.show(count, saved)
        self.query_one("#menu").display = False
        self.update_header()
        self.focus_result()

    def result_view(self, count):
        if isinstance(count, tfidf.TfidfCount):
            return self.query_one("#tfidf-view", TfidfView)
        if isinstance(count, sentences.SentenceCount):
            return self.query_one("#sentences-view", SentencesView)
        return self.query_one("#words-view", WordsView)

    def focus_result(self):
        if self.last_count is None:
            return
        first = {"words-view": "#frequencies", "sentences-view": "#longest", "tfidf-view": "#passages"}
        view = self.result_view(self.last_count)
        focus_now(view.query_one(first[view.id]))

    # Messages from the result views -----------------------------------------------------
    def on_open_source(self, message: OpenSource):
        self.open_in_reader(message.source)

    def on_status(self, message: Status):
        self.query_one("#result-status", Static).update(message.text)

    def open_in_reader(self, source):
        """Ask the reader, through Neovim's terminal, to open a source."""
        request = json.dumps({"version": 1, "op": "open_source", "source": source},
                             ensure_ascii=True, separators=(",", ":"))
        encoded = base64.b64encode(request.encode("ascii")).decode("ascii")
        # Textual's own driver writes the sequence between frames, as it does
        # for its clipboard sequence, so it never splits a screen update.
        if self._driver is not None:
            self._driver.write(self.SOURCE_SEQUENCE.format(encoded))
        self.query_one("#result-status", Static).update("Asked the reader to open this passage.")

    # Export -------------------------------------------------------------------------------
    def export(self, table_format):
        count, status = self.last_count, self.query_one("#result-status", Static)
        if not isinstance(count, words.Count) or count.reference is None:
            status.update("Nothing to export: a comparison with a reference is what is exported.")
            return
        if not self.state_file:
            status.update("Not exported: this reader session has no workspace, so ESSENCE writes nothing.")
            return
        if self.exporting:
            # The engine cannot be stopped midway; a second export would write a second file.
            status.update("An export is still running; wait for it to finish.")
            return
        self.exporting = True
        status.update("Checking the sources again and exporting…")
        self.export_table(count, table_format)

    @work(thread=True, exclusive=True, group="export")
    def export_table(self, count, table_format):
        try:
            outcome = words.export(count, table_format)
        except (words.EngineMissing, ValueError, OSError) as error:
            outcome = error
        try:
            self.call_from_thread(self.finish_export, count, outcome)
        except RuntimeError:
            pass

    def finish_export(self, count, outcome):
        self.exporting = False
        if count is not self.last_count:
            return
        self.query_one("#result-status", Static).update(
            f"Not exported: {outcome}" if isinstance(outcome, Exception) else f"Exported: {outcome}")

    # Function words (a declared display list; counts never change) --------------------
    def function_words(self):
        """The bundled list, or None when this installation does not have it."""
        if self._function_words is None:
            try:
                from sol.essence.function_words import load_function_words
            except ImportError:
                self._function_words = False
            else:
                self._function_words = load_function_words()
        return self._function_words or None

    # Reference ---------------------------------------------------------------------------
    def action_reference(self, tab="encyclopedia", method=None, entry=None):
        # One reference screen for the session: its searches and selections
        # stay as they were left between openings.
        if "reference" not in self._installed_screens:
            self.install_screen(ReferenceScreen(), "reference")
        screen = self.get_screen("reference")
        screen.open(tab, method)
        if not isinstance(self.screen, ReferenceScreen):
            self.push_screen(screen, self.use_method)
            self.update_layout()
        if entry is not None:
            self.call_after_refresh(lambda: self.reveal_entry(screen, entry))

    @staticmethod
    def reveal_entry(screen, entry):
        """Show catalog entry `entry`, by its stable option ID, even outside a search."""
        from textual.widgets import OptionList
        field = screen.query_one("#encyclopedia-search", Input)
        if field.value:
            with screen.prevent(Input.Changed):
                field.value = ""
            screen.filter_browser("encyclopedia")
        listing = screen.query_one("#encyclopedia-list", OptionList)
        listing.highlighted = listing.get_option_index(str(entry + 1))
        screen.update_browser("encyclopedia")

    def action_method(self):
        study = self.last_run[0] if self.last_run else self.query_one("#menu", StudyMenu).study
        method = ("word-comparison" if study == "words" and self.last_run and self.last_run[2] != "none"
                  else STUDY_METHODS[study])
        self.action_reference("methods", method)

    def use_method(self, method):
        if method is None:
            self.call_after_refresh(self.restore_focus)
            return
        menu = self.query_one("#menu", StudyMenu)
        study = METHOD_STUDIES[method]
        choices = {"study": study}
        if method == "word-comparison" and menu.reference == "none":
            choices["reference"] = "book" if self.context["corpus"] else "file"
        menu.set_choices(**choices)
        self.update_header()
        self.action_menu()

    def restore_focus(self):
        if self.query_one("#menu").display:
            focus_now(self.query_one("#menu"))
        else:
            self.focus_result()

    def action_keys(self):
        if self.screen.query("HelpPanel"):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()

    def check_action(self, action, parameters):
        if action == "cancel_count":
            return self.counting and not isinstance(self.screen, ReferenceScreen)
        return True

    def action_cancel_count(self):
        self.cancel_count()

    # Following the reader ------------------------------------------------------------------
    def follow_reader_theme(self):
        """Take the theme the reader last wrote; anything unreadable or unknown is ignored."""
        try:
            with open(self.theme_file, encoding="utf-8") as stream:
                name = stream.read(32).strip()
        except (OSError, UnicodeDecodeError):
            return
        if name in TEXTUAL_THEMES and self.theme != TEXTUAL_THEMES[name]:
            self.theme = TEXTUAL_THEMES[name]

    def restyle_open_screens(self, theme):
        """Textual restyles only the base screen; an open palette or modal keeps the old colors."""
        for screen in self.screen_stack[1:]:
            self.stylesheet.update(screen, animate=False)
        self.update_header()
        if isinstance(self.screen, ReferenceScreen):
            self.screen.update_header()

    def follow_reader_position(self):
        """Take the reader's latest checked position; "this passage" then means it."""
        try:
            from sol.interchange.essence import read_position
            position = read_position(self.position_file)
        except (ImportError, OSError, ValueError):
            return
        key = (position["reference"]["reference"]["target_id"], position["cursor_offset"])
        if key == self.position_seen:
            return
        self.position_seen = key
        moved = position["reference"]["reference"]["target_id"] != self.context["reference"]["reference"]["target_id"]
        self.context = dict(self.context, reference=position["reference"], cursor_offset=position["cursor_offset"],
                            selection=position["selection"], label=position["label"])
        if moved and self.last_run is not None and self.last_run[1] in ("passage", "section"):
            self.reading_moved = True
        self.update_header()

    # Layout ----------------------------------------------------------------------------------
    def on_resize(self, event):
        # App.size is updated by Textual after this handler; use the event's
        # destination width so the breakpoint changes on this resize.
        self.update_layout(event.size.width, event.size.height)
        self.call_after_refresh(self.reflow)

    def update_layout(self, width=None, height=None):
        width = self.size.width if width is None else width
        height = self.size.height if height is None else height
        for screen in self.screen_stack:
            screen.set_class(width < 100, "-compact")
            screen.set_class(width < 60, "-small")
            screen.set_class(height < 30, "-short")

    def reflow(self):
        self.query_one("#menu", StudyMenu).refresh_menu()
        if self.last_count is not None:
            self.result_view(self.last_count).reflow()

    def action_leave(self):
        self.count_serial += 1  # A count still running is abandoned.
        if self.state_file:
            if isinstance(self.screen, ReferenceScreen):
                from textual.widgets import TabbedContent
                view = self.screen.query_one("#catalogs", TabbedContent).active
            else:
                view = "workspace"
            save_state(self.state_file, {
                "version": 1, "screen": view,
                "origin": self.context["reference"]["reference"]["target_id"]})
        self.exit(0)
