"""Build the Linux MobileKonekt distribution with PyInstaller."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
WORK = ROOT / ".build" / "pyinstaller"
name = "MobileKonekt"


def main() -> None:
    if not (ROOT / "dist" / "index.html").is_file():
        raise SystemExit("Frontend build missing. Run `npm run build:web` first.")

    RELEASE.mkdir(exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    separator = os.pathsep
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        name,
        "--distpath",
        str(RELEASE),
        "--workpath",
        str(WORK),
        "--specpath",
        str(WORK),
        "--add-data",
        f"{ROOT / 'dist'}{separator}dist",
        "--add-data",
        f"{ROOT / 'backend' / 'admin_assets'}{separator}backend/admin_assets",
        str(ROOT / "backend" / "__main__.py"),
    ]

    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except FileNotFoundError as error:
        raise SystemExit(
            "PyInstaller is required. Install it with "
            "`python -m pip install -r requirements.txt`."
        ) from error

    spec_file = WORK / f"{name}.spec"
    if spec_file.exists():
        spec_file.unlink()
    pycache = ROOT / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)

    print(f"Packaged {RELEASE / name / name}")


if __name__ == "__main__":
    main()
