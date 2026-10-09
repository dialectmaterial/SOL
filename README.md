# `sol` — Hegel's *Science of Logic* in the terminal

`sol` is a page-aware reader for the supplied Cambridge edition of Hegel's
*Science of Logic*. It selects only Hegel's main text: George di Giovanni's
introduction, front matter, appendix, bibliography, and index are excluded.

Every reading states its virtual location, the edition's printed page, and PDF
page, then folds prose to a comfortable terminal width.

## Install locally

1. Install Poppler's `pdftotext` command if it is not already available:

   ```sh
   sudo apt install poppler-utils
   ```

2. Put the PDF in the directory from which you want to run `sol`:

   ```sh
   cp /path/to/georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf \
      ./georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf
   ```

   `sol` now looks for that filename in the current directory. You can still
   use `--pdf /path/to/file.pdf` for a one-off location.

3. Make the program available as `sol`:

   ```sh
   chmod +x /path/to/sol.py
   mkdir -p ~/.local/bin
   ln -sf /path/to/sol.py ~/.local/bin/sol
   ```

   Ensure `~/.local/bin` is in your `PATH`, then open a new terminal.

## Read

```sh
sol
sol --width 72
sol --read /BEING/05-determinateness-quality/02-existence.txt
sol --structure
```

The default command chooses a random paragraph from anywhere in the Logic. Its
heading tells you exactly where it belongs; `--read` restricts the selection to
one logical division or one virtual text file.

## Browse the virtual filesystem

```sh
sol --shell
```

Inside it, `cd`, `ls`, `pwd`, `tree`, `read`, and `cat` work on the three root
directories: `BEING`, `ESSENCE`, and `CONCEPT`.

```text
sol:/$ cd BEING
sol:/BEING$ ls
sol:/BEING$ cd 05-determinateness-quality
sol:/BEING/05-determinateness-quality$ read 02-existence.txt
```

Directories are logical sections and files are chapter-level stretches of
prose. `read` and `cat` choose a random readable paragraph from the selected
location; no thousands of generated text files are needed.

## Future packaging

The program is still intentionally a single file. For pip installation later,
move it into a package and add a `pyproject.toml` console-script entry pointing
at `sol:main`.
