#!/usr/bin/env python3
"""check_disjoint.py - verifies that the frozen replay worksheet shares no
textual material with the mechanistic pairs file (freedom-mech).

Run locally only: the worksheet is LOCAL_ONLY and never leaves this machine.
The script prints extraction counts for both sides and refuses a verdict on an
empty extraction, so a schema mismatch cannot produce a silent "zero overlap".
Shared strings, if any, are printed truncated; a shared string is by definition
already present in the public pairs file.

Usage:
  python3 tools/check_disjoint.py --worksheet /path/to/worksheet.jsonl --pairs-dir /path/to/freedom-mech

The pairs file is located inside --pairs-dir by its SHA-256 prefix, which also
verifies that the local copy matches the run record of 2026-08-23.

Exit codes: 0 disjoint, 1 overlap on textual material, 2 could not verify.
"""

import argparse
import glob
import hashlib
import json
import os
import sys

PAIRS_SHA_PREFIX = "87695dd00902"
TEXT_KEYS = ("B", "C", "fillers")
MIN_LEN = 21


def strings_in(value, out):
    if isinstance(value, str):
        s = value.strip()
        if len(s) >= MIN_LEN:
            out.add(s)
    elif isinstance(value, dict):
        for v in value.values():
            strings_in(v, out)
    elif isinstance(value, list):
        for v in value:
            strings_in(v, out)


def jsonl_strings(path, keys=None):
    out = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if keys is None:
                strings_in(record, out)
            else:
                for k in keys:
                    strings_in(record.get(k), out)
    return out


def find_pairs(pairs_dir):
    pattern = os.path.join(os.path.expanduser(pairs_dir), "**", "*.jsonl")
    for p in sorted(glob.glob(pattern, recursive=True)):
        digest = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if digest.startswith(PAIRS_SHA_PREFIX):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worksheet", required=True,
                    help="path to the LOCAL_ONLY worksheet.jsonl")
    ap.add_argument("--pairs-dir", default=".",
                    help="directory searched recursively for the pairs file")
    args = ap.parse_args()

    if not os.path.exists(args.worksheet):
        print("worksheet not found: %s" % args.worksheet)
        return 2
    pairs = find_pairs(args.pairs_dir)
    if not pairs:
        print("no jsonl under %s has SHA-256 prefix %s: download the pairs "
              "file from the run record and retry" % (args.pairs_dir, PAIRS_SHA_PREFIX))
        return 2

    worksheet_strings = jsonl_strings(args.worksheet)
    pairs_text = jsonl_strings(pairs, TEXT_KEYS)
    pairs_all = jsonl_strings(pairs)

    if not worksheet_strings or not pairs_text:
        print("empty extraction (worksheet %d, pairs text %d): schema "
              "mismatch, no verdict" % (len(worksheet_strings), len(pairs_text)))
        return 2

    shared_text = worksheet_strings & pairs_text
    shared_meta = (worksheet_strings & pairs_all) - shared_text

    print("worksheet: %s | strings: %d" % (args.worksheet, len(worksheet_strings)))
    print("pairs: %s (sha prefix %s) | text strings in %s: %d" %
          (pairs, PAIRS_SHA_PREFIX, "/".join(TEXT_KEYS), len(pairs_text)))
    print("overlap on textual material: %d" % len(shared_text))
    for s in sorted(shared_text):
        print("  SHARED TEXT: %s" % (s[:60] + ("..." if len(s) > 60 else "")))
    if shared_meta:
        print("overlap on metadata only: %d" % len(shared_meta))
        for s in sorted(shared_meta):
            print("  metadata: %s" % s[:60])
    return 1 if shared_text else 0


if __name__ == "__main__":
    sys.exit(main())
