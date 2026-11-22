from __future__ import annotations

import argparse
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sflasher", description="ShlepaFlash CLI")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--check", action="store_true", help="Run environment checks and exit")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.check:
        from .app import run_checks
        return 0 if run_checks() else 1

    from .app import run
    return run()
