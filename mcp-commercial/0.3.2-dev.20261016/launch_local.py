# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Minimal stdio launcher; reads no credential file and never uses ambient deps."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from install_local import isolated_python

ROOT = Path(__file__).resolve().parent


def main():
    if os.name != "posix":
        print("This candidate requires POSIX private-file permission checks; Windows is unsupported.", file=sys.stderr)
        return 2
    try:
        python = isolated_python(ROOT)
    except (OSError, ValueError):
        print("Candidate .venv is missing or not isolated. Run install_local.py first.", file=sys.stderr)
        return 2
    # Ignore Python-specific environment/user-site injection, while retaining the
    # private config path supplied explicitly by the chosen local MCP host.
    os.execv(str(python), [str(python), "-E", "-s", str(ROOT / "sales_mcp.py")])
    return 2  # execv does not return after success.


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError:
        print("Candidate launcher could not start its isolated interpreter.", file=sys.stderr)
        raise SystemExit(2)
