# Changes

## Unreleased

## 0.1.0 — 30 October 2026

The first tagged version of SOL. It needs the supported Cambridge / George di
Giovanni PDF, which is converted locally once and never bundled. Earlier,
day-by-day entries are in the
[full development changelog](https://github.com/dialectmaterial/SOL/blob/96cf945e6b4603626928e77cd37e595943257f2b/CHANGELOG.md).

### Reading (BEING)

- One Neovim-backed reader, in the terminal or in a window of its own with
  `sol-window`, and a minimal `sol --shell` that saves nothing.
- Your exact position is saved and resumed; the outline, printed-page jumps,
  quick markers and named landmarks move through the book.
- Search covers the whole book and steps through every occurrence.
- The printed source is available as a crop or as the whole page in Zathura or
  another PDF viewer, following your reading.
- Attributed notes, footnotes and pages appear beside the text.
- Themes are Mocha, Latte, Paper, Night or your terminal's colors. Reader keys
  can be moved in `keys.json`.

### Analysis (ESSENCE)

- A result-first workspace opens beside the reader with `E` and follows your
  passage, in the reader's own colors.
- Studies cover word counts, every occurrence in context, comparison, TF-IDF
  and sentence lengths, with declared function words that can be hidden.
- Every study is also available headlessly through `sol essence`.
- A modest encyclopedia describes each method with attributed quotations.

### Corpus and services (CORE)

- Verified corpus generations, portable references and a checked source
  conversion, with the corpus kept outside the repository.

### Project

- Licensed under GPL-3.0-or-later.
- Code is organized under the logical divisions of
  [SPECULATIVE](docs/SPECULATIVE.md). The 21 October cleanup removed `sol-kitty`,
  `sol compare`, the legacy PDF reader and the empty `shell`, `corpus` and
  `extraction` extras.
- Agent coordination files left the tree; open work is in GitHub issues, and
  task reports are in pull requests.

### Known issue

- Opening a passage from fullscreen ESSENCE leaves ESSENCE covering the reader
  ([#142](https://github.com/dialectmaterial/SOL/issues/142)).
