# Results render evidence

Invented public corpus from `tests/fixtures_corpus.py`, real study engines,
Paper theme; no private book or workspace. Each text file records the terminal
cells, preserving spaces beside bold text. The PNG compares Textual screenshots
before (left) and after (right); screenshots can misplace spaces beside bold.

| Study | 80×24 before / after | 120×40 before / after |
| --- | --- | --- |
| Words | [before](before-words-80x24.txt) / [after](after-words-80x24.txt) | [before](before-words-120x40.txt) / [after](after-words-120x40.txt) |
| Comparison | [before](before-comparison-80x24.txt) / [after](after-comparison-80x24.txt) | [before](before-comparison-120x40.txt) / [after](after-comparison-120x40.txt) |
| Sentences | [before](before-sentences-80x24.txt) / [after](after-sentences-80x24.txt) | [before](before-sentences-120x40.txt) / [after](after-sentences-120x40.txt) |
| TF-IDF | [before](before-tfidf-80x24.txt) / [after](after-tfidf-80x24.txt) | [before](before-tfidf-120x40.txt) / [after](after-tfidf-120x40.txt) |

[80×24 comparison screenshot pair](comparison-80x24.png).
Real Textual terminal-driver captures through tmux, with **invented** selected:
[80×24](terminal-comparison-80x24.txt), [120×40](terminal-comparison-120x40.txt).
The full context reads “An invented passage makes this installed research…”.
Native terminal captures checked this spacing in all five reader themes;
ANSI Terminal's palette is not represented by Textual's SVG screenshot.

Pilot coverage is in `SmallResultsTests` in `tests/test_essence_tui.py`, including
resizing, source navigation, long Unicode words and undefined measures. The
fixtures here are review evidence rather than exact screenshot assertions.
