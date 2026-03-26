#!/usr/bin/env python3
"""Build standalone executable using PyInstaller.

Usage:
    python build.py              # default onedir build
    python build.py --onefile    # single-file executable
    python build.py --debug      # keep console window for debugging

Output goes to dist/AutonomousWorld/
"""

import os
import sys
import shutil
import argparse


def _parse_args():
    parser = argparse.ArgumentParser(description="Build Autonomous World executable")
    parser.add_argument("--onefile", action="store_true",
                        help="Build a single-file executable instead of a directory")
    parser.add_argument("--debug", action="store_true",
                        help="Keep console window visible for debugging")
    parser.add_argument("--clean", action="store_true",
                        help="Clean build artifacts before building")
    return parser.parse_args()


def _clean_build_dirs():
    """Remove previous build artifacts."""
    for d in ("build", "dist"):
        path = os.path.join(os.path.dirname(__file__), d)
        if os.path.isdir(path):
            print(f"Removing {path}")
            shutil.rmtree(path)
    spec = os.path.join(os.path.dirname(__file__), "AutonomousWorld.spec")
    if os.path.isfile(spec):
        os.remove(spec)


def build(onefile: bool = False, debug: bool = False):
    """Run PyInstaller with the appropriate options."""
    try:
        import PyInstaller.__main__
    except ImportError:
        print("ERROR: PyInstaller is not installed.")
        print("Install it with:  pip install pyinstaller")
        sys.exit(1)

    root = os.path.dirname(os.path.abspath(__file__))
    entry = os.path.join(root, "play.py")

    if not os.path.isfile(entry):
        print(f"ERROR: Entry point not found: {entry}")
        sys.exit(1)

    # Determine data directories to include
    data_dirs = []
    for name in ("game", "data"):
        src = os.path.join(root, name)
        if os.path.isdir(src):
            sep = ";" if sys.platform == "win32" else ":"
            data_dirs.append(f"--add-data={name}{sep}{name}")

    # Build args
    args = [
        entry,
        f"--name=AutonomousWorld",
        "--onefile" if onefile else "--onedir",
    ]
    args.extend(data_dirs)

    # Hidden imports that PyInstaller may miss
    hidden = ["pygame", "numpy", "json", "threading", "socket"]
    for mod in hidden:
        args.append(f"--hidden-import={mod}")

    # Console / windowed
    if not debug:
        args.append("--noconsole")

    # Icon (optional)
    icon = os.path.join(root, "icon.ico")
    if os.path.isfile(icon):
        args.append(f"--icon={icon}")
    elif sys.platform == "darwin":
        icns = os.path.join(root, "icon.icns")
        if os.path.isfile(icns):
            args.append(f"--icon={icns}")

    # Spec file
    args.append(f"--specpath={root}")

    print("=" * 60)
    print("Building Autonomous World")
    print(f"  Mode:    {'onefile' if onefile else 'onedir'}")
    print(f"  Console: {'yes' if debug else 'no'}")
    print(f"  Data:    {[d.split('=')[1] for d in data_dirs]}")
    print("=" * 60)

    PyInstaller.__main__.run(args)

    print()
    print("Build complete! Output in dist/AutonomousWorld")
    if not onefile:
        print("Run with: dist/AutonomousWorld/AutonomousWorld")


if __name__ == "__main__":
    args = _parse_args()
    if args.clean:
        _clean_build_dirs()
    build(onefile=args.onefile, debug=args.debug)
