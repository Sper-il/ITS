"""
print_baseline_sha.py — Print SHA-256 of every baseline snapshot, so we have
a machine-readable summary to compare against the post-refactor capture.

Run:
    python tests/snapshots/print_baseline_sha.py > BASELINE_SHA256.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def main():
    summary = {}
    for p in sorted(THIS_DIR.glob("*.json")):
        if p.name == "BASELINE_SHA256.json":
            continue
        with open(p, "r", encoding="utf-8") as f:
            wrapped = json.load(f)
        summary[p.name] = wrapped["sha256"]
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    print()  # trailing newline


if __name__ == "__main__":
    main()
