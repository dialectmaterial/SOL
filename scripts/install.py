#!/usr/bin/env python3
"""Complete checkout installation; no install hooks or downloads while reading.

Debian/Ubuntu native packages are installed with explicit consent. A missing or
old editor is supplied privately from a pinned, checksum-verified upstream build.
Other systems can use this installer once their native dependencies are present.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sol.terminal.runtime import NEOVIM_VERSION, managed_neovim

# Digests published with the official v0.11.6 release assets, not fetched at install.
# https://github.com/neovim/neovim/releases/expanded_assets/v0.11.6
ARCHIVES = {
    ("Linux", "x86_64"): ("nvim-linux-x86_64", "2fc90b962327f73a78afbfb8203fd19db8db9cdf4ee5e2bef84704339add89cc"),
    ("Linux", "aarch64"): ("nvim-linux-arm64", "8ddc0c101846145e830b17bbca50782ca9307eee4fab539d9e2ddaf8793c06f1"),
    ("Darwin", "arm64"): ("nvim-macos-arm64", "d5ee93b67630d5a87f3d336d0f7e8b2fe6973aa653d3cc93b82b820e6538c1dd"),
    ("Darwin", "x86_64"): ("nvim-macos-x86_64", "6e665bb0a711cf974050e0f7183dbb696b1e7425814eb87df7cb094a49054a06"),
}
TOOLS = {"pipx": "pipx", "git": "git", "pdftotext": "poppler-utils",
         "pdftohtml": "poppler-utils", "pdftoppm": "poppler-utils",
         "java": "default-jre-headless", "kitty": "kitty", "zsh": "zsh"}


def missing_packages():
    tools = dict(TOOLS)
    if platform.system() == "Linux":
        tools.update({"wl-copy": "wl-clipboard", "xclip": "xclip"})
    missing = {package for tool, package in tools.items() if not shutil.which(tool)}
    if shutil.which("java"):
        try:
            result = subprocess.run([shutil.which("java"), "-version"], capture_output=True, text=True, timeout=5)
            version = re.search(r'version "(?:1\.)?(\d+)', result.stderr + result.stdout)
            if result.returncode or version is None or int(version[1]) < 11:
                missing.add("default-jre-headless")
        except (OSError, subprocess.TimeoutExpired):
            missing.add("default-jre-headless")
    return sorted(missing)


def check_existing_commands():
    """Never let --force replace an unrelated command with the same name."""
    for name in ("sol", "sol-kitty", "sol-corpus", "sol-corpus-check"):
        location = shutil.which(name)
        if location:
            target = Path(location).resolve()
            if target.parent.name != "bin" or target.parent.parent.name != "sol-organizes-logic":
                raise ValueError(f"An existing {name} is not a normal SOL pipx command: {location}. "
                                 "Inspect and preserve it before installing; nothing was overwritten.")


def editor_works(executable):
    if not executable:
        return False
    try:
        result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    version = re.match(r"NVIM v(\d+)\.(\d+)", result.stdout)
    return bool(result.returncode == 0 and version and tuple(map(int, version.groups())) >= (0, 11))


def extract_checked(archive, destination):
    """Refuse traversal, external links and special files even in pinned assets."""
    destination = destination.resolve()
    for member in archive.getmembers():
        path = (destination / member.name).resolve()
        if not path.is_relative_to(destination):
            raise ValueError("Neovim archive contains an unsafe path")
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError("Neovim archive contains a special file")
        if member.issym() or member.islnk():
            target = (path.parent if member.issym() else destination) / member.linkname
            if not target.resolve().is_relative_to(destination):
                raise ValueError("Neovim archive contains an external link")
    # data_filter is also available in patched Python 3.10 releases.
    if hasattr(tarfile, "data_filter"):
        archive.extractall(destination, filter="data")
    else:
        # Each extraction is rechecked after any earlier symlink was created.
        for member in archive.getmembers():
            if not (destination / member.name).resolve().is_relative_to(destination):
                raise ValueError("Neovim archive traverses an earlier symlink")
            archive.extract(member, destination)


def install_editor():
    destination = managed_neovim().parents[1]
    if destination.exists():
        raise ValueError(f"Private Neovim exists but is unusable: {destination}. It was not overwritten.")
    asset = ARCHIVES.get((platform.system(), platform.machine()))
    if asset is None:
        raise ValueError("No managed Neovim build for this platform. Install Neovim 0.11+ with your package manager.")
    name, expected = asset
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".neovim-install-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        package = stage / "editor.tar.gz"
        address = f"https://github.com/neovim/neovim/releases/download/v{NEOVIM_VERSION}/{name}.tar.gz"
        digest, size = hashlib.sha256(), 0
        with urlopen(address, timeout=60) as response, package.open("wb") as output:
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > 64 * 1024 * 1024:
                    raise ValueError("Neovim download exceeded its size budget")
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != expected:
            raise ValueError("Neovim download checksum mismatch; nothing was installed")
        with tarfile.open(package, "r:gz") as archive:
            extract_checked(archive, stage)
        if not editor_works(stage / name / "bin" / "nvim"):
            raise ValueError("The downloaded Neovim cannot run here; install a compatible system build instead.")
        (stage / name).rename(destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="approve the displayed installation plan")
    parser.add_argument("--check", action="store_true", help="show prerequisites without changing anything")
    parser.add_argument("--source", default=str(ROOT), help="local checkout or git+https URL to install")
    args = parser.parse_args(argv)
    try:
        packages = missing_packages()
        private = managed_neovim()
        native = editor_works(private) if private.exists() else editor_works(shutil.which("nvim"))
        print("SOL installation plan")
        print("Native packages: " + (", ".join(packages) if packages else "already available"))
        print("Neovim: " + ("already available" if native else f"private verified {NEOVIM_VERSION} build"))
        print(f"Python application and all feature dependencies: pipx install --force {args.source}")
        print("Your PDF, corpus, workspaces and editor/terminal settings are not modified.")
        if args.check:
            return 0
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            raise ValueError("Run this installer as your normal user, not with sudo.")
        if packages and not shutil.which("apt-get"):
            raise ValueError("Automatic native setup currently supports Debian/Ubuntu. Install the listed tools "
                             "using your system package manager, then rerun this installer.")
        check_existing_commands()
        if not args.yes and input("Proceed with this installation? [y/N] ").strip().lower() not in {"y", "yes"}:
            print("Nothing changed.")
            return 0
        if packages:
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", *packages], check=True)
            remaining = missing_packages()
            if remaining:
                raise ValueError("Tools are still unavailable on PATH after native setup: " + ", ".join(remaining))
        if not native:
            install_editor()
        subprocess.run([shutil.which("pipx") or "pipx", "install", "--force", args.source], check=True)
        subprocess.run([shutil.which("pipx") or "pipx", "ensurepath"], check=True)
        print("SOL installed. Open a new terminal if PATH changed, then run sol.\n"
              "First launch asks for your supported PDF if no corpus is configured.")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"SOL installation stopped: {error}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nInstallation cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
