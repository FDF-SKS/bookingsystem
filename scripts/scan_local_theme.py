#!/usr/bin/env python3
"""Start a local Django dev server and scan it for theme contrast issues.

Uses the Playwright scanner in `check_theme_contrast.py` (run with the system
Python that has Playwright installed) against a temporary `runserver`.
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8011"
ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "check_theme_contrast.py"
# Playwright lives on the system Python (3.10), not the project venv.
PLAYWRIGHT_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"


def main() -> int:
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", "127.0.0.1:8011", "--noreload"],
        cwd=ROOT / "src",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE_URL + "/", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise SystemExit("Dev server did not start in time.")

        return subprocess.run(
            [PLAYWRIGHT_PYTHON, str(SCANNER), BASE_URL],
            check=False,
        ).returncode
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
