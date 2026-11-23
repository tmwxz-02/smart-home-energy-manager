"""Build dist/fai.zip: the source code to upload to a hosting service.

Run:  python make_zip.py
Leaves out your data (data/), caches, the old prototype zips and the PDF.
Inside the zip everything is in a folder called "fai".
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INCLUDE_DIRS = ["backend", "frontend", "samples", "tests", "notebooks", "docs"]
INCLUDE_FILES = ["app.py", "main.py", "wsgi.py", "make_zip.py", "README.md", "DEFENSE.md", "DEFENSE_SCRIPT.md",
                 "DEPLOY.md", "start.bat", "start_network.bat", "open_in_vscode.bat", ".gitignore"]


def main():
    target = ROOT / "dist" / "fai.zip"
    target.parent.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in INCLUDE_FILES:
            path = ROOT / name
            if path.is_file():
                archive.write(path, f"fai/{name}")
                count += 1
        for folder in INCLUDE_DIRS:
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    archive.write(path, f"fai/{path.relative_to(ROOT).as_posix()}")
                    count += 1
    print(f"Created {target} ({count} files, {target.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
