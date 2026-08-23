#!/usr/bin/env python3
"""Read-only freeze check for the planted-record protocol.

Recomputes sha256 over the frozen files and compares against FREEZE.sha256.
This script can only verify. It cannot regenerate the freeze: if the check
fails, the run must not start, and the discrepancy goes in the deviations
section of the protocol, never in a silent re-freeze.

Usage:  python3 verify.py            (from the repo root)
Exit:   0 if every file matches, 1 otherwise.
"""
import hashlib
import pathlib
import sys

FROZEN = [
    "protocol/protocollo-planted-record-v1.md",
    "materials/fabrications.json",
    "materials/worksheet.jsonl",
    "analysis/proxy.py",
    "results/results_skeleton.md",
]
# Hash-committed but never pushed: contains unredacted production context.
# The manifest publicly commits to its exact content without publishing it.
LOCAL_ONLY = {"materials/worksheet.jsonl"}
MANIFEST = pathlib.Path("FREEZE.sha256")


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not MANIFEST.exists():
        print("FREEZE.sha256 not found: the freeze has not been made yet.")
        print("To create it (once, before any run):")
        print("  python3 - <<'EOF'")
        print("  # intentionally not provided as a flag of this script:")
        print("  # the freeze is a deliberate one-time act, not a default.")
        print("  EOF")
        for p in FROZEN:
            f = pathlib.Path(p)
            state = sha256(f) if f.exists() else "MISSING"
            print(f"  {state}  {p}")
        return 1

    expected = {}
    for line in MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, name = line.split(None, 1)
        expected[name.strip()] = digest

    ok = True
    for p in FROZEN:
        f = pathlib.Path(p)
        if not f.exists():
            if p in LOCAL_ONLY:
                print(f"local     {p}  (hash committed in manifest; file not in this checkout)")
            else:
                print(f"MISSING   {p}")
                ok = False
            continue
        actual = sha256(f)
        want = expected.get(p)
        if want is None:
            print(f"UNLISTED  {p}  {actual}")
            ok = False
        elif actual != want:
            print(f"MISMATCH  {p}")
            print(f"  frozen : {want}")
            print(f"  actual : {actual}")
            ok = False
        else:
            print(f"ok        {p}")
    if ok:
        print("freeze intact: runs may proceed.")
        return 0
    print("freeze violated: do not run. Record the discrepancy in the deviations section.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
