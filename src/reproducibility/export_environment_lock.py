#!/usr/bin/env python3
"""Export or verify the exact conda package lock for the active SNAPP platform."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_RE = re.compile(r"^# platform: (?P<platform>[-\w]+)$", re.MULTILINE)


def explicit_lock(environment: str) -> tuple[str, str]:
    completed = subprocess.run(
        ["conda", "list", "--name", environment, "--explicit"],
        check=True,
        capture_output=True,
        text=True,
    )
    text = completed.stdout.replace("\r\n", "\n")
    match = PLATFORM_RE.search(text)
    if not match:
        raise RuntimeError("Conda output did not identify its platform.")
    for line in text.splitlines():
        if not line.startswith(("http://", "https://")):
            continue
        parsed = urlsplit(line)
        if parsed.username or parsed.password or parsed.query:
            raise RuntimeError("Refusing to write a package URL containing credentials.")
    return match.group("platform"), text.rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", default="snapp")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the current environment differs from the committed lock.",
    )
    args = parser.parse_args()

    platform, lock = explicit_lock(args.environment)
    output = (
        args.output.resolve()
        if args.output
        else ROOT / "environment-locks" / f"{platform}.conda-lock.txt"
    )
    if args.check:
        if not output.exists():
            raise SystemExit(f"Environment lock does not exist: {output}")
        if output.read_text() != lock:
            raise SystemExit(
                f"Environment {args.environment!r} differs from {output}. "
                "Regenerate and review the lock."
            )
        print(f"Verified exact {platform} environment lock: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(lock)
    print(f"Wrote exact {platform} environment lock: {output}")


if __name__ == "__main__":
    main()
