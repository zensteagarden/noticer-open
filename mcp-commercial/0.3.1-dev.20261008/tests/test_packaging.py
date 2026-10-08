# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Offline installer/launcher tests. No package downloads or user configuration."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import commercial_mcp
import install_local as install
import launch_local as launch


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.envdir = self.root / ".venv"
        (self.envdir / "bin").mkdir(parents=True)
        (self.envdir / "bin/python").write_text("fixture interpreter placeholder")
        (self.envdir / "pyvenv.cfg").write_text("include-system-site-packages = false\nversion = 3.12.14\n")
        self.errors = io.StringIO()

    def test_development_version_cannot_be_confused_with_published_release(self):
        version = (install.ROOT / "VERSION").read_text().strip()
        self.assertEqual(version, "0.3.1.dev20261008")
        self.assertNotEqual(version, "0.1.0")

    def test_dependency_subprocess_environment_excludes_user_config_and_pip_secrets(self):
        with patch.dict(os.environ, {"PIP_INDEX_URL": "https://fixture-secret.invalid", "PIP_EXTRA_INDEX_URL": "https://fixture-extra.invalid", "PIP_TRUSTED_HOST": "fixture", "PYTHONPATH": "/fixture/injection", "NOTICER_COMMERCIAL_CONFIG_FILE": "/fixture/private-config"}):
            env = install.safe_environment()
        for key in ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST", "PYTHONPATH", "NOTICER_COMMERCIAL_CONFIG_FILE"):
            self.assertNotIn(key, env)
        self.assertEqual(env["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(env["PIP_KEYRING_PROVIDER"], "disabled")
        self.assertEqual(env["NETRC"], os.devnull)

    def test_isolated_python_uses_candidate_venv(self):
        self.assertEqual(install.isolated_python(self.root), self.envdir / "bin/python")

    def test_shared_site_environment_is_refused(self):
        (self.envdir / "pyvenv.cfg").write_text("include-system-site-packages = true\n")
        with self.assertRaises(ValueError):
            install.isolated_python(self.root)

    def test_missing_venv_is_refused_without_ambient_fallback(self):
        with self.assertRaises(ValueError):
            install.isolated_python(self.root / "missing")

    def test_install_uses_only_official_index_and_wheels(self):
        with patch.object(install, "run", return_value=0) as runner, redirect_stdout(io.StringIO()):
            self.assertEqual(install.install_or_check(root=self.root), 0)
        command = [str(x) for x in runner.call_args_list[0].args[0]]
        self.assertEqual(command[command.index("--index-url") + 1], "https://pypi.org/simple")
        self.assertIn("--only-binary=:all:", command)
        self.assertNotIn("--extra-index-url", command)
        self.assertEqual(len(runner.call_args_list), 4)

    def test_dependency_failure_propagates_nonzero_without_running_tests(self):
        with patch.object(install, "run", return_value=17) as runner:
            self.assertEqual(install.install_or_check(root=self.root), 17)
        self.assertEqual(runner.call_count, 1)

    def test_test_failure_propagates_nonzero(self):
        with patch.object(install, "run", side_effect=[0, 42]) as runner:
            self.assertEqual(install.install_or_check(check_only=True, root=self.root), 42)
        self.assertEqual(runner.call_count, 2)

    def test_check_only_never_installs_or_contacts_index(self):
        with patch.object(install, "run", return_value=0) as runner, redirect_stdout(io.StringIO()):
            self.assertEqual(install.install_or_check(check_only=True, root=self.root), 0)
        commands = [[str(x) for x in call.args[0]] for call in runner.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertFalse(any("install" in command or "--index-url" in command for command in commands))

    def test_windows_installer_is_explicitly_unsupported(self):
        with patch.object(install.os, "name", "nt"), redirect_stderr(self.errors):
            self.assertEqual(install.install_or_check(root=self.root), 2)
        self.assertIn("Windows credential-file ACLs are not validated", self.errors.getvalue())

    def test_windows_configuration_refuses_before_reading_any_credential(self):
        with patch.object(commercial_mcp.os, "name", "nt"), patch.object(commercial_mcp, "private_read") as reader:
            with self.assertRaises(commercial_mcp.buyer.BuyerError):
                commercial_mcp.load_adapter("/fixture/private.json")
        reader.assert_not_called()

    def test_windows_launcher_fails_before_interpreter_selection(self):
        with patch.object(launch.os, "name", "nt"), patch.object(launch, "isolated_python") as selector, redirect_stderr(self.errors):
            self.assertEqual(launch.main(), 2)
        selector.assert_not_called()

    def test_launcher_executes_exact_isolated_stdio_entry(self):
        python = self.envdir / "bin/python"
        with patch.object(launch, "isolated_python", return_value=python), patch.object(launch.os, "execv", side_effect=RuntimeError("fixture stop")) as execute:
            with self.assertRaisesRegex(RuntimeError, "fixture stop"):
                launch.main()
        execute.assert_called_once_with(str(python), [str(python), "-E", "-s", str(launch.ROOT / "sales_mcp.py")])

    def test_launcher_missing_venv_never_falls_back(self):
        with patch.object(launch, "isolated_python", side_effect=ValueError("fixture")), redirect_stderr(self.errors), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launch.main(), 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("Run install_local.py first", self.errors.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
