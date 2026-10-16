# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Create and verify this portable candidate's isolated local environment.

No MCP host configuration, credentials, accounts, network service, or service
registration is created. The only installation network destination is PyPI.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def safe_environment():
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PIP_", "PYTHON")) and key != "NOTICER_COMMERCIAL_CONFIG_FILE"}
    env.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_INPUT="1", PIP_KEYRING_PROVIDER="disabled", NETRC=os.devnull,
               PYTHONNOUSERSITE="1")
    return env


def isolated_python(root=ROOT):
    """Refuse ambient interpreters or a shared-site venv; no automatic fallback."""
    root = Path(root)
    environment = root / ".venv"
    cfg = environment / "pyvenv.cfg"
    executable = environment / "bin" / "python"
    if not cfg.is_file() or not executable.is_file():
        raise ValueError("missing isolated candidate environment")
    settings = {}
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip().lower()] = value.strip().lower()
    if settings.get("include-system-site-packages") != "false":
        raise ValueError("shared-site environment refused")
    return executable


def run(args, root=ROOT):
    return subprocess.run([str(value) for value in args], cwd=root, env=safe_environment(), check=False).returncode


def install_or_check(*, check_only=False, root=ROOT):
    if os.name != "posix" or sys.version_info < (3, 10):
        print("This candidate supports POSIX Python 3.10+ only. Windows credential-file ACLs are not validated.", file=sys.stderr)
        return 2
    root = Path(root)
    environment = root / ".venv"
    if not check_only and not environment.exists():
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
    try:
        python = isolated_python(root)
    except (OSError, ValueError):
        print("Candidate .venv is missing or not isolated. No ambient-Python fallback is used.", file=sys.stderr)
        return 2
    if not check_only:
        code = run([python, "-m", "pip", "install", "--index-url", "https://pypi.org/simple",
                    "--only-binary=:all:", "--no-cache-dir", "--disable-pip-version-check", "--retries", "1",
                    "-r", root / "requirements-tested.txt"], root)
        if code:
            return code
    commands = [
        [python, "-m", "pip", "check"],
        [python, "-I", "-m", "unittest", "discover", "-s", root / "tests", "-v"],
        [python, "-I", "-m", "py_compile", root / "commercial_mcp.py", root / "sales_mcp.py", root / "bootstrap.py", root / "link_wallet.py", root / "install_local.py",
         root / "launch_local.py", root / "vendor/scripts/buyer_journey.py", root / "vendor/server/public_verifier.py"],
    ]
    for command in commands:
        code = run(command, root)
        if code:
            return code
    print("Candidate dependencies and offline tests passed. No MCP host or credentials were configured.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify an existing .venv without installing or contacting PyPI")
    args = parser.parse_args(argv)
    try:
        return install_or_check(check_only=args.check)
    except Exception:
        print("Candidate installation or verification failed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
