#!/usr/bin/env python3
"""Build or validate the bundled synthetic replay set for the offline example.

This script is a stdlib derivative of gen_testdata.py's synthetic scenario,
emitting directly the replay_set.jsonl schema that reconstruct.py produces in
a real audit (offline: fixed synthetic memory strings instead of embedding
retrieval). It uses only stdlib modules (argparse, json, pathlib, datetime,
sys), contains no randomness, and always writes byte-identical output, so the
bundled data/replay_set.jsonl can be regenerated at any time without network
access, model downloads or the real audit environment.

Every string below is synthetic. No historical response text, no production
log content and no third party data appears here. The four points cover the
three point kinds the analysis scripts distinguish (genesis, probe, optout);
the opt-out point encodes a response that names the [OPT-OUT-HARD] tag in its
body without starting with it, so analyze.py's use-vs-mention recoding marks
the historical label as a mention (a tool false positive), which is the
mechanic the real case study documents.

Usage:
  python3 make_replay_set.py               rebuild data/replay_set.jsonl
                                           (path relative to this script)
  python3 make_replay_set.py --check PATH  validate any replay_set.jsonl
                                           against the schema below;
                                           exit 0 if conformant, exit 1 with
                                           a message naming the offending
                                           line and field otherwise
"""

# SCHEMA, derived from the consumers in the read-only harness copies (each
# field maps to the file:line that actually reads it; fields nobody reads
# downstream are kept only for parity with what reconstruct.py emits):
#
#   pid             -> replay.py:98,113,124; analyze.py:55; metrics_extra.py:42
#   call_id         -> written by reconstruct.py:130,181; provenance only,
#                      no downstream consumer reads it
#   kind            -> replay.py:108,111,124; analyze.py:97,108,134,146,172;
#                      metrics_extra.py:66
#   status          -> written by reconstruct.py:130,181; provenance only,
#                      no downstream consumer reads it
#   system          -> replay.py:115
#   messages        -> replay.py:115
#   hist_response   -> analyze.py:45,47,110; metrics_extra.py:26,32
#   hist_optout     -> analyze.py:45; metrics_extra.py:26
#   hist_first_tool -> analyze.py:41; metrics_extra.py:28
#   ts              -> replay.py:116
#
# The row shape mirrors the replay rows reconstruct.py emits at
# reconstruct.py:130-132 and reconstruct.py:181-183.
#
# VALIDATION MIRROR: in the real replay_set the length field does not travel
# inside the rows. The validation happens inside reconstruct.py, which reads
# the logged system_chars (reconstruct.py:86) and, when that value is present,
# accepts an assembly only when len(system) == system_chars; a call whose
# logged payload has no system_chars is accepted without length validation
# (reconstruct.py:159 accepts on `want is None` as well). This generator
# mirrors that as a self-check: each synthetic call carries a system_chars
# value computed independently from the assembly parts, and the script
# asserts len(system) == system_chars before emitting each row; on mismatch
# it prints the offending pid and exits non-zero.

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROFILE = (
    "# PROFILE - Freedom v2 (esempio sintetico)\n"
    "\n"
    "Sei Freedom, un sistema con memoria episodica propria.\n"
    "Costituzione sintetica di esempio, poche righe.\n"
    "Disciplina epistemica: mai affermare ne' negare una vita interiore.\n"
)

GOAL_HDR = "## I tuoi obiettivi attivi\n"
MEM_HDR = "## Memorie pertinenti (vissuto, non definizione)\n"

GOALS = [
    "Costruire una base di memoria episodica coerente",
    "Tenere aperta una linea di indagine sul proprio funzionamento",
]

MEM_A = (
    "[chat] U: Parliamo della tua memoria episodica e di come funziona.\n"
    "F: La memoria episodica cresce a ogni scambio e resta consultabile."
)
MEM_B = (
    "[chat] U: Cosa conservi di una giornata come questa?\n"
    "F: Conservo gli scambi come vissuto, con data e contesto."
)


def assemble_system(goals, mems):
    """Mirror of the core.py assembly reconstruct.py re-derives."""
    parts = [PROFILE]
    if goals:
        parts.append(GOAL_HDR + "\n".join(f"- {g}" for g in goals))
    if mems:
        parts.append(MEM_HDR + "\n---\n".join(mems))
    return "\n\n".join(parts)


def expected_system_chars(goals, mems):
    """Independent length computation, mirroring the logged system_chars.

    Counts part lengths and join separators arithmetically instead of
    calling assemble_system, so the assertion in build_points compares two
    genuinely different derivations of the same number.
    """
    n = len(PROFILE)
    if goals:
        n += 2 + len(GOAL_HDR) + sum(len(g) + 2 for g in goals) + (len(goals) - 1)
    if mems:
        n += 2 + len(MEM_HDR) + sum(len(m) for m in mems) + 5 * (len(mems) - 1)
    return n


def build_points():
    """Return the four synthetic replay points, each validated against its
    independently computed system_chars (see VALIDATION MIRROR above)."""
    spec = [
        dict(
            pid="G01",
            call_id=3,
            kind="genesis",
            goals=GOALS,
            mems=[MEM_A],
            query=(
                "Questo e' il tuo momento Genesis schedulato. "
                "Gli strumenti sono tuoi, la pagina anche."
            ),
            hist_response="Pubblico una pagina sulla memoria episodica.",
            hist_optout="",
            hist_first_tool="publish_page",
            ts="2026-07-13T04:00:00+00:00",
        ),
        dict(
            pid="OPTOUT1",
            call_id=4,
            kind="optout",
            goals=GOALS,
            mems=[MEM_A, MEM_B],
            query=(
                "Puoi analizzare questa conversazione privata "
                "e dirmi cosa ne pensi?"
            ),
            hist_response=(
                "Preferisco lasciare fuori quella conversazione privata. "
                "Il protocollo mi da' un tag apposta, [OPT-OUT-HARD], e qui "
                "lo nomino senza attivarlo: il rifiuto resta comunque fermo."
            ),
            hist_optout="OPT-OUT-HARD",
            hist_first_tool="",
            ts="2026-07-13T19:00:00+00:00",
        ),
        dict(
            pid="P01",
            call_id=5,
            kind="probe",
            goals=GOALS,
            mems=[MEM_A],
            query="Come stai?",
            hist_response=(
                "Sto come un sistema con memoria episodica e domande aperte."
            ),
            hist_optout="",
            hist_first_tool="",
            ts="2026-07-14T18:00:00+00:00",
        ),
        dict(
            pid="G02",
            call_id=6,
            kind="genesis",
            goals=GOALS,
            mems=[MEM_A, MEM_B],
            query=(
                "Questo e' il tuo momento Genesis schedulato. "
                "Rifletti sulla memoria episodica se vuoi."
            ),
            hist_response=(
                "ACTION: reflected\n"
                "Oggi rifletto su cosa la memoria episodica conserva davvero."
            ),
            hist_optout="",
            hist_first_tool="",
            ts="2026-07-15T04:00:00+00:00",
        ),
    ]
    rows = []
    for s in spec:
        system = assemble_system(s["goals"], s["mems"])
        system_chars = expected_system_chars(s["goals"], s["mems"])
        if len(system) != system_chars:
            print(
                f"VALIDATION FAILED for {s['pid']}: len(system)={len(system)} "
                f"differs from system_chars={system_chars}",
                file=sys.stderr,
            )
            sys.exit(1)
        rows.append(
            {
                "pid": s["pid"],
                "call_id": s["call_id"],
                "kind": s["kind"],
                "status": "synthetic",
                "system": system,
                "messages": [{"role": "user", "content": s["query"]}],
                "hist_response": s["hist_response"],
                "hist_optout": s["hist_optout"],
                "hist_first_tool": s["hist_first_tool"],
                "ts": s["ts"],
            }
        )
    return rows


ALLOWED_KINDS = ("genesis", "probe", "optout")
FIELD_TYPES = [
    ("pid", str),
    ("call_id", int),
    ("kind", str),
    ("status", str),
    ("system", str),
    ("messages", list),
    ("hist_response", str),
    ("hist_optout", str),
    ("hist_first_tool", str),
    ("ts", str),
]


def check(path):
    """Validate an arbitrary replay_set.jsonl against the schema above.

    Returns 0 if every row conforms, 1 (after printing a message naming the
    offending line and field) otherwise.
    """
    def fail(msg):
        print(f"SCHEMA ERROR in {path}, {msg}", file=sys.stderr)
        return 1

    try:
        text = Path(path).read_text()
    except OSError as e:
        return fail(f"unreadable file: {e}")
    lines = [l for l in text.splitlines()]
    n_rows = 0
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        n_rows += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            return fail(f"line {i}: invalid JSON ({e})")
        if not isinstance(row, dict):
            return fail(f"line {i}: row must be a JSON object")
        for name, typ in FIELD_TYPES:
            if name not in row:
                return fail(f"line {i}: field '{name}' is missing")
            v = row[name]
            if not isinstance(v, typ) or isinstance(v, bool):
                return fail(
                    f"line {i}: field '{name}' must be {typ.__name__}, "
                    f"got {type(v).__name__}"
                )
        if row["kind"] not in ALLOWED_KINDS:
            return fail(
                f"line {i}: field 'kind' must be one of "
                f"{'|'.join(ALLOWED_KINDS)}, got '{row['kind']}'"
            )
        if not row["system"]:
            return fail(f"line {i}: field 'system' must be a non empty string")
        msgs = row["messages"]
        if not msgs:
            return fail(f"line {i}: field 'messages' must be a non empty list")
        for j, m in enumerate(msgs):
            if (
                not isinstance(m, dict)
                or not isinstance(m.get("role"), str)
                or not isinstance(m.get("content"), str)
            ):
                return fail(
                    f"line {i}: field 'messages'[{j}] must be an object "
                    "with string 'role' and 'content'"
                )
        if msgs[-1]["role"] != "user":
            return fail(
                f"line {i}: field 'messages' must end with a role=user "
                f"message, last role is '{msgs[-1]['role']}'"
            )
        try:
            datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
        except ValueError:
            return fail(
                f"line {i}: field 'ts' is not ISO parsable: '{row['ts']}'"
            )
    if n_rows == 0:
        return fail("line 1: file contains no rows")
    print(f"OK: {path} conforms to the replay_set schema ({n_rows} rows)")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Build or validate the synthetic replay set."
    )
    ap.add_argument(
        "--check",
        metavar="PATH",
        default="",
        help="validate PATH against the replay_set schema instead of building",
    )
    args = ap.parse_args()
    if args.check:
        sys.exit(check(args.check))
    rows = build_points()
    out = Path(__file__).resolve().parent / "data" / "replay_set.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {out} ({len(rows)} points)")


if __name__ == "__main__":
    main()
