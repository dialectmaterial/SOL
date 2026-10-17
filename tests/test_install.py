"""Installation planning and archive safety; no network or system mutations."""
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import install


class InstallerTests(unittest.TestCase):
    def test_check_is_read_only_even_when_everything_is_missing(self):
        with patch.object(install, "missing_packages", return_value=["poppler-utils"]), \
                patch.object(install, "editor_works", return_value=False), \
                patch.object(install, "install_editor", side_effect=AssertionError("No download")), \
                patch.object(install.subprocess, "run", side_effect=AssertionError("No install")), \
                patch("builtins.input", side_effect=AssertionError("No prompt")), redirect_stdout(StringIO()):
            self.assertEqual(install.main(["--check"]), 0)

    def test_declining_plan_changes_nothing(self):
        with patch.object(install, "missing_packages", return_value=[]), \
                patch.object(install, "editor_works", return_value=False), \
                patch.object(install.os, "geteuid", return_value=1000), \
                patch.object(install, "check_existing_commands"), \
                patch.object(install.subprocess, "run", side_effect=AssertionError("No install")), \
                patch("builtins.input", return_value="n"), redirect_stdout(StringIO()):
            self.assertEqual(install.main([]), 0)

    def test_existing_native_tools_need_only_a_full_pipx_install(self):
        with patch.object(install, "missing_packages", return_value=[]), \
                patch.object(install, "editor_works", return_value=True), \
                patch.object(install.os, "geteuid", return_value=1000), \
                patch.object(install.shutil, "which", return_value="/invented/pipx"), \
                patch.object(install, "check_existing_commands"), \
                patch.object(install.subprocess, "run") as run, redirect_stdout(StringIO()):
            self.assertEqual(install.main(["--yes", "--source", "."]), 0)
        self.assertEqual(run.call_args_list[0].args[0], ["/invented/pipx", "install", "--force", "."])
        self.assertEqual(run.call_args_list[1].args[0], ["/invented/pipx", "ensurepath"])

    def test_installer_refuses_to_overwrite_unrelated_sol(self):
        with patch.object(install.shutil, "which", return_value="/invented/bin/sol"), \
                self.assertRaisesRegex(ValueError, "nothing was overwritten"):
            install.check_existing_commands()

    def test_java_8_is_not_mistaken_for_a_complete_installation(self):
        from types import SimpleNamespace
        with patch.object(install.shutil, "which", return_value="/invented/tool"), \
                patch.object(install.subprocess, "run", return_value=SimpleNamespace(returncode=0,
                    stdout="", stderr='java version "1.8.0_442"')):
            self.assertIn("default-jre-headless", install.missing_packages())

    def test_archive_refuses_traversal_absolute_paths_devices_and_external_links(self):
        for name, kind, link in (("../escape", tarfile.REGTYPE, ""),
                                 ("/escape", tarfile.REGTYPE, ""),
                                 ("fifo", tarfile.FIFOTYPE, ""),
                                 ("link", tarfile.SYMTYPE, "../../escape"),
                                 ("link", tarfile.LNKTYPE, "/escape")):
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as temporary:
                data = BytesIO()
                with tarfile.open(fileobj=data, mode="w") as archive:
                    member = tarfile.TarInfo(name)
                    member.type, member.linkname = kind, link
                    archive.addfile(member)
                data.seek(0)
                with tarfile.open(fileobj=data) as archive, self.assertRaises(ValueError):
                    install.extract_checked(archive, Path(temporary))
                self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_archive_extracts_an_ordinary_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = BytesIO()
            with tarfile.open(fileobj=data, mode="w") as archive:
                member = tarfile.TarInfo("nvim/bin/nvim")
                member.size = 7
                archive.addfile(member, BytesIO(b"example"))
            data.seek(0)
            with tarfile.open(fileobj=data) as archive:
                install.extract_checked(archive, Path(temporary))
            self.assertEqual((Path(temporary) / "nvim/bin/nvim").read_bytes(), b"example")
