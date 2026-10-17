# Reading trial: Being, Nothing, Becoming

15 October 2026. Which surface lets you follow the argument with fewer
interruptions? This private trial is not an engine decision.

## Start at the same place

From the repository root, inspect the named sample:

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial beginning inventory
```

`beginning` selects complete Chapter 1, Being, including remarks and linked notes.
Metadata supplies counts, pages, and corpus binding from actual records. This
preset targets the current English Cambridge corpus; an unrecognized hierarchy
is refused, not guessed. No UUID copying is needed.

For short orientation, replace `beginning` with `opening` throughout: this selects
Being–Nothing–Becoming before Remark 1, not the complete Becoming section. The
current corpus supplies 3 paragraphs without linked notes there; the complete
chapter has 55 paragraphs and 25 linked notes (printed pages 59–82). These are
observations, not fixed selection limits; available notes are never removed.
Compare that same extent even if baseline navigation permits leaving it.

Run these one at a time in your usual terminal, preferably Alacritty:

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial beginning baseline --width 72
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial beginning tui --width 72
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial beginning html --output /tmp/sol-beginning-trial.html
xdg-open /tmp/sol-beginning-trial.html
```

Choose a new HTML filename if it exists. Keep book text private and outside Git.
No launch opens or saves a personal workspace.

## Read before inspecting the interface

Choose your session length; 30–45 minutes is an invitation, not a requirement
or a goal to finish the chapter. Read the same portion in each surface,
changing their order when repeating: familiarity can make a later view easier.

Follow the transitions. Does a paragraph boundary interrupt the earlier thought?
Is emphasis legible? Do labels help or compete with prose? Keep terminal measures
equal; adjust browser size for comfort, not supposed equivalence between terminal
columns and CSS characters.

Then try one detour where available:

| Surface | Small exercise | Current limit |
| --- | --- | --- |
| Baseline | `c` for source context, `f` for focus; search `/being`, open a result, then Alt-Left to return. Select a short styled phrase with `v` and movement. | One active record at a time; this trial is temporary. |
| Continuous terminal | Read across a passage boundary with `j/k`, use `b/n`, inspect `c`, and select within one passage. Clear selection with Escape before crossing. Quit with `q`. | No search, persistent position, note UI, or workspace action. |
| Typeset HTML | Inspect Source context and an available attributed note. Export a selected span, change window/font size, then restore its packet. | A research packet is not an annotation or workspace save; selection stays inside one passage. |

Check one difficult passage against your book/PDF, using displayed page references.
Record uncertainty rather than silently correcting the corpus.

## Keep a five-line friction log

```text
Surface and sample extent:
Where my reading was interrupted:
What I did to recover my place or thought:
Typography, notes, or source uncertainty:
One change that would help me continue:
```

“Nothing interrupted me” is useful too. No score or winning surface is assumed.
Bring back one concrete example to guide the next refinement.
