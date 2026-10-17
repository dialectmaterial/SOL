# Reader engines: bounded upstream audit

Research date: 15 October 2026. Status: comparison evidence, not an engine
adoption decision. No upstream application was installed, forked, or run for
this audit. No code, corpus content, or assets were imported.

The current terminal reader remains the baseline. This report asks which mature
components could improve sustained reading while SOL retains canonical Markdown,
verified paragraph identity, attribution, and source-codepoint selection. It
does not propose a replacement architecture or a new ESSENCE implementation.

## Recommendation

Compare continuous terminal reading with a small offline typeset surface first.
That separates the question “does proportional, continuous text help reading?”
from “should SOL adopt an entire ebook application?”

Of the projects inspected, **foliate-js is the clearest component-level candidate**
for a later rendering experiment. The others are valuable reading references or
optional external viewers, but none was established here as a drop-in SOL
workspace engine. This is an engineering judgment, not an upstream claim.

| Project | Best provisional role for SOL | Cost or mismatch to investigate |
| --- | --- | --- |
| Foliate / foliate-js | Learn from the desktop reader; consider the separate JS renderer behind an adapter | Unstable renderer API, document security, DOM-to-source mapping, section boundaries |
| Readest | Study parallel reading, selection actions, and typeset interaction | Full application stack and its own forks; not merely a renderer dependency |
| Zathura | Optional facsimile viewer; restrained keyboard/jump-list inspiration | Page-oriented plugin interface, not canonical paragraph/span identity |
| Okular | Optional source-review viewer with annotations and page opening | Qt/KDE embedding and page/area model add substantial scope |
| KOReader | Study reading ergonomics, notes, and reflow; possible external ebook host | Device-oriented application and engine-specific location vocabulary |
| Sioyek | Study context-preserving comparison/portals; optional PDF host | PDF coordinates and viewer databases are not SOL semantic relations |
| calibre | Strong external typeset comparison baseline | Its locations, conversion, and annotation storage need explicit isolation |

## Observed upstream revisions and licences

These are identifiable versions/snapshots observed through upstream pages, not
claims about locally installed versions. Branch links can change; a prototype
that imports code must record its exact revision and dependencies first.

| Project | Observed revision | Licence evidence |
| --- | --- | --- |
| Foliate | [3.3.0 release](https://github.com/johnfactotum/foliate/releases/tag/3.3.0), commit `6846cf62ef3ff4f0162f1b288f44d6dcce5f1a19` | Desktop application: [GPL-3.0-or-later in upstream README](https://github.com/johnfactotum/foliate#license) |
| foliate-js | [commit `78914aef4466eb960965702401634c2cb348e9b1`](https://github.com/johnfactotum/foliate-js/commit/78914aef4466eb960965702401634c2cb348e9b1), also the head shown by the inspected commit listing | [MIT licence at that revision](https://github.com/johnfactotum/foliate-js/blob/78914aef4466eb960965702401634c2cb348e9b1/LICENSE) |
| Readest | [v0.12.16](https://github.com/readest/readest/releases/tag/v0.12.16), release page identifies `3cc39ad` | [AGPL-3.0-or-later in README](https://github.com/readest/readest#license) |
| Zathura | [Tag listing shows 2026.07.18](https://github.com/pwmt/zathura/tags), identifying `4fad4e4` | [zlib-style licence text on inspected development branch](https://github.com/pwmt/zathura/blob/develop/LICENSE) |
| Okular | [26.08.2, dated 8 October 2026](https://apps.kde.org/okular/) | Application lists GPL-2.0+; inspected [core document header](https://github.com/KDE/okular/blob/master/core/document.h) specifies GPL-2.0-or-later |
| KOReader | [v2026.07.1](https://github.com/koreader/koreader/releases/tag/v2026.07.1), release page identifies `9192014` | Repository identifies [AGPL-3.0](https://github.com/koreader/koreader); inspect individual dependencies separately |
| Sioyek | [v2.0.0](https://github.com/ahrm/sioyek/releases/tag/v2.0.0), release page identifies `7cb948f` | [GPL v3 licence file](https://github.com/ahrm/sioyek/blob/v2.0.0/LICENSE) |
| calibre | [9.16, dated 9 October 2026](https://calibre-ebook.com/whats-new) | [GPL v3 in viewer source header](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/gui2/viewer/web_view.py) |

The short hashes above are precisely what the respective release pages exposed;
full resolved commits were not independently obtained for those entries. No
compatibility or redistribution clearance follows from this table. A later
integration needs a file/dependency/font licence inventory for the actual pinned
combination, including format backends. No such combination is adopted here.

## What can actually be reused?

### Foliate is not foliate-js

The desktop application is built around GJS, GTK4, libadwaita, and WebKitGTK.
Its [installation documentation](https://github.com/johnfactotum/foliate#installation)
describes source builds and Flatpak distribution. Forking that application would
therefore mean maintaining a desktop application, not adding one Python reader
dependency.

The separate [foliate-js interface documentation](https://github.com/johnfactotum/foliate-js/blob/main/README.md)
provides ES modules, a custom book interface, `view.open`, `goTo`, DOM `Range`
locations, and relocation events. It explicitly describes its own API as unstable
and unreleased. Its demo is not a complete reader. The documentation also warns
that iframe sandboxing alone is insufficient for scripted ebooks and requires
an appropriate Content Security Policy. An MIT library licence does not remove
those operational responsibilities.

Its scrolling claims need care: the README both mentions a limitation on
continuous scrolling and describes `flow="scrolled"`.
The inspected [paginator source at the pinned revision](https://github.com/johnfactotum/foliate-js/blob/78914aef4466eb960965702401634c2cb348e9b1/paginator.js)
does implement scrolled flow, but keeps one active section document and loads an
adjacent section when navigation reaches its boundary. That is evidence for
within-section scrolling, **not proof of simultaneous, seamless multi-section
reading or selection**. Test the exact intended section size and transitions.

Proposed reuse boundary: a custom book adapter can expose generated, verified
SOL text to the renderer; relocation/selection must then be translated back to
SOL identity. Never promote a CFI, DOM path, scroll fraction, or browser page to
canonical identity. Pin and test the adapter rather than tracking upstream
`main` implicitly. No foliate-js dependency is added by this report.

### Readest

The [README](https://github.com/readest/readest) describes a Next.js/Tauri
application with scrolled/paged reading, highlighting, notes, and parallel views.
Its current [submodule configuration](https://github.com/readest/readest/blob/main/.gitmodules)
points to Readest-maintained forks of both foliate-js and Tauri. This makes
Readest a useful complete-application benchmark, not evidence that vanilla
foliate-js provides every Readest feature.

The inspected [Tauri configuration](https://github.com/readest/readest/blob/main/apps/readest-app/src-tauri/tauri.conf.json)
contains Linux deb/rpm/AppImage configuration and a network-capable CSP with
inline/eval allowances. That is a configuration observation, **not a vulnerability
finding**. SOL should not copy that policy into a narrowly offline reader.
Judgment: study its interaction, but do not inherit its cloud integrations,
application data model, or full build/update burden merely to obtain typography.

### Zathura and Okular

Zathura's [document-plugin guide](https://pwmt.org/projects/zathura/plugins/development/)
describes shared-object backends implementing document operations. Its
[manual](https://pwmt.org/projects/zathura/documentation/) offers configurable
motion, jump history, search, and page-oriented persistence. These are useful
interaction references and an external facsimile workflow. Writing a SOL plugin
would still require translating the page-facing interface; it is not an existing
semantic Markdown adapter.

Okular has a real reusable C++ core and KPart, but its
[build definition](https://github.com/KDE/okular/blob/master/CMakeLists.txt) brings
Qt/KDE dependencies and generators. Its
[document interface](https://github.com/KDE/okular/blob/master/core/document.h)
exposes page viewports, text selection, and annotations, not SOL's paragraph IDs.
Its [command-line interface](https://docs.kde.org/stable_kf6/en/okular/okular/command-line-options.html)
already supports opening at a page and searching a string.
Judgment: prefer a separately launched source viewer before considering embedding;
page/search navigation must be labelled approximate unless independently mapped.

### KOReader

Upstream documents a configurable, plugin-extensible reader with reflowable and
fixed-layout formats, primarily designed for e-ink devices.
[Project overview](https://github.com/koreader/koreader).
Its [CRE document wrapper](https://github.com/koreader/koreader/blob/master/frontend/document/credocument.lua)
exposes XPointer locations, EPUB CFI conversion, text extraction, and navigation.
These are integration footholds, but this audit did not establish an API stability
guarantee or equivalence to SOL codepoints. Judgment: borrow its low-distraction
reading and note-return ideas; an adapter or plugin would need exact location
round-trip tests and would not eliminate ownership of the SOL identity boundary.

### Sioyek

The [usage documentation](https://sioyek-documentation.readthedocs.io/en/latest/usage.html)
describes a helper window for portal destinations, return history, and separate
local/shared databases with JSON export/import. These are compelling references
for comparing a distant passage without losing the argument's thread. The
project remains a PDF-oriented viewer; portal coordinates and imported data must
not become SOL semantic relations automatically.

There is observable version drift: the [2.0 installation guide](https://sioyek-documentation.readthedocs.io/en/latest/installation.html)
discusses Qt5, whereas the [development README](https://github.com/ahrm/sioyek)
requires Qt6.7/6.8. A future handoff must target a tested executable/version,
not assume commands and build requirements from different branches compose.

### calibre

The [viewer manual](https://manual.calibre-ebook.com/viewer.html) documents flow
and paged modes, remembered position, selection/highlights, a reference mode,
and return from links. The [viewer CLI](https://manual.calibre-ebook.com/generated/en/ebook-viewer.html)
accepts `--open-at` locations, TOC hrefs, references, and search. These make it a
useful external comparison surface without a fork. Its
[implementation](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/gui2/viewer/web_view.py)
uses Qt WebEngine rather than a standalone renderer-only Python API.

The viewer manual also says EPUB bookmarks can be written into the EPUB unless
disabled. Therefore any later trial should use a disposable generated copy,
not the canonical corpus or a sole source file. Reference-mode paragraph numbers
are application locations, not replacements for permanent SOL IDs. No conversion
or external annotation import was performed in this audit.

## Linux, Wayland, and packaging boundaries

| Candidate | Upstream evidence | Still needs an actual host test |
| --- | --- | --- |
| Foliate | GTK/WebKitGTK and Flatpak instructions, linked above | Native Wayland selection, resize, focus/return, and portals |
| Readest | Linux bundle configuration, linked above | Exact packaged renderer, Wayland/XWayland backend, clipboard and offline behavior |
| Zathura | [2026.07.18 build](https://github.com/pwmt/zathura/blob/2026.07.18/meson.build) uses GTK4 and versioned plugin API/ABI | Distribution-matched plugins; current manual still identifies 0.5.12 |
| Okular | [Official distribution/Flatpak guidance](https://okular.kde.org/download/) | Qt Wayland plugin, file permissions and instance/page targeting |
| KOReader | [Upstream desktop guide](https://github.com/koreader/koreader/wiki/Installation-on-desktop-Linux) describes deb/AppImage/Flatpak; [current SDL device source](https://github.com/koreader/koreader/blob/master/frontend/device/sdl/device.lua) handles X11/Wayland naming | Backend packaged into the selected release, selection and resize ergonomics |
| Sioyek | Official installation guide distinguishes upstream binaries from third-party packages | Exact release's Qt/display plugins and helper-window behavior |
| calibre | Viewer manual supports standalone `ebook-viewer` on Linux | Packaged Qt WebEngine/Wayland combination and safe disposable-profile behavior |

Linux support does not prove native Wayland behavior for a particular package.
No row above is a manual compatibility result. None makes BEING a Kitty
application or requires replacing Alacritty. Flatpak access and external process
handoffs must be explicit; Nix packaging is a later reproducibility task, not a
prerequisite for this comparison.

## Identity and safety gates for any adoption

These are SOL requirements and engineering judgments, not capabilities claimed
for all of the upstream readers.

1. **One identity model.** Keep corpus/record identity, source fingerprint, and
   half-open source-codepoint spans. External locations are derived coordinates.
   Do not infer exact spans by taking the first matching quotation substring.
2. **Prove DOM mapping.** DOM character data is measured in UTF-16 code units,
   whereas SOL uses Unicode codepoints. DOM element endpoints also count child
   nodes. See the [DOM range and character-data standard](https://dom.spec.whatwg.org/)
   and its [string/code-unit definitions](https://infra.spec.whatwg.org/#string).
   Map typed boundaries explicitly across emphasis/code/link nodes; test astral
   characters, combining sequences, repeats, and forward/backward selections.
   Reject surrogate-interior, stale, ambiguous, or unsupported mappings.
3. **Treat layout as derived.** Reflow, pagination, CSS hyphenation, and glyph
   ligatures must not change canonical text. A position saved as paragraph plus
   source offset must survive font/width changes. Multi-paragraph selection must
   preserve ordered existing spans, not introduce an unrelated global character ID.
4. **Keep the prototype local and inert.** Escape text; do not execute corpus
   HTML, scripts, event handlers, or remote resources. Bundle assets locally,
   enforce a restrictive CSP, and expose no filesystem/workspace command bridge.
   A future foliate-js iframe/Blob integration needs its own tested CSP—not a
   policy copied from another app or reliance on a sandbox attribute alone.
5. **Compare with evidence.** Test long prose, emphasis, note-return, search,
   selection, resize/reopen, and long section boundaries. Measure cold opening
   and long-document responsiveness in the actual package. Distinguish automated
   mappings from real Alacritty/Wayland/browser use and from sustained human reading.
6. **Stop before adoption.** Require an explicit decision on reading benefit,
   exact selection fidelity, accessibility, security, licensing, distribution,
   and ongoing maintenance. A complete application fork has not earned that cost
   merely by looking attractive in screenshots.

Unresolved: real upstream-application ergonomics on this machine; verified
bidirectional adapters for their location formats; whole-book memory/performance;
screen-reader behavior; dependency/font inventory; and whether any typeset
surface actually improves sustained philosophical reading for the user.
