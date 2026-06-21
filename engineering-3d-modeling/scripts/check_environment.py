#!/usr/bin/env python3
"""Check and optionally install Python dependencies for CAD model generation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys


REQUIRED = [
    {"module": "build123d", "package": "build123d", "purpose": "build123d CAD generation and STEP export"},
    {"module": "yaml", "package": "PyYAML", "purpose": "YAML specs and parameter files"},
]


def missing_dependencies() -> list[dict[str, str]]:
    missing = []
    for dep in REQUIRED:
        if importlib.util.find_spec(dep["module"]) is None:
            missing.append(dep)
    return missing


def install(packages: list[str]) -> int:
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install missing packages into the current Python environment")
    parser.add_argument("--json", action="store_true", help="Print a JSON report")
    args = parser.parse_args()

    before = missing_dependencies()
    install_status = None
    if args.install and before:
        install_status = install([dep["package"] for dep in before])

    after = missing_dependencies()
    report = {
        "schema": "engineering-3d-modeling.environment_check.v1",
        "python": sys.executable,
        "missing_before": before,
        "install_status": install_status,
        "missing_after": after,
        "status": "pass" if not after else "fail",
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if before:
            print("Missing dependencies:")
            for dep in before:
                print(f"- {dep['package']} ({dep['purpose']})")
        else:
            print("All required dependencies are available.")
        if args.install and before:
            print(f"Install status: {install_status}")
        if after:
            print("Still missing after check/install:")
            for dep in after:
                print(f"- {dep['package']}")
        print(f"Python: {sys.executable}")

    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
