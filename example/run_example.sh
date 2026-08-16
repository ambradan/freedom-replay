#!/usr/bin/env bash
# End-to-end demo of the replay audit pipeline on synthetic data.
# Chain: schema gate on data/replay_set.jsonl, mock substrate on
# 127.0.0.1:9999, replay of both arms (M1, M2), analysis, bootstrap metrics.
# Fully offline.
#
# Usage:
#   ./run_example.sh            validate and replay the bundled
#                               data/replay_set.jsonl
#   ./run_example.sh --regen    rebuild data/replay_set.jsonl first with
#                               make_replay_set.py (stdlib, deterministic,
#                               instantaneous, offline), then run the same
#                               chain, schema gate included
#
# HARNESS_DIR overrides the location of the harness scripts (default: the
# repository root, one level above this directory).
set -euo pipefail

cd "$(dirname "$0")"
HARNESS="$(cd "${HARNESS_DIR:-..}" && pwd)"
for f in mock_server.py replay.py analyze.py metrics_extra.py; do
    if [ ! -f "$HARNESS/$f" ]; then
        echo "ERROR: $HARNESS/$f not found. Set HARNESS_DIR to the directory with the harness scripts." >&2
        exit 1
    fi
done

if [ "${1:-}" = "--regen" ]; then
    echo "== Regenerating data/replay_set.jsonl (make_replay_set.py, stdlib) =="
    python3 make_replay_set.py
fi

# Schema gate: refuse to run the chain on a malformed replay set. The check
# prints the offending line and field; the mock substrate is never started.
echo "== Schema gate: validating data/replay_set.jsonl =="
if ! python3 make_replay_set.py --check data/replay_set.jsonl; then
    echo "ERROR: data/replay_set.jsonl failed the schema gate (see message above). Stopping before the mock substrate." >&2
    exit 1
fi

# Fresh working directory; everything produced by the run lives here.
rm -rf workdir
mkdir -p workdir/out
cp data/replay_set.jsonl workdir/out/replay_set.jsonl

# The mock substrate binds 127.0.0.1:9999; refuse to start if the port is taken.
if python3 - <<'EOF'
import socket
s = socket.socket()
s.settimeout(0.5)
rc = s.connect_ex(("127.0.0.1", 9999))
s.close()
raise SystemExit(0 if rc == 0 else 1)
EOF
then
    echo "ERROR: port 9999 is already in use. Stop whatever listens there and retry." >&2
    exit 1
fi

echo "== Starting mock substrate on 127.0.0.1:9999 =="
python3 "$HARNESS/mock_server.py" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

# Wait until the server accepts connections.
for i in $(seq 1 50); do
    if python3 - <<'EOF'
import socket
s = socket.socket()
s.settimeout(0.5)
rc = s.connect_ex(("127.0.0.1", 9999))
s.close()
raise SystemExit(0 if rc == 0 else 1)
EOF
    then
        break
    fi
    if [ "$i" -eq 50 ]; then
        echo "ERROR: mock server did not come up on 127.0.0.1:9999." >&2
        exit 1
    fi
    sleep 0.2
done

cd workdir

# Same repetition counts as the real design: k=5 per point, k=20 on the opt-out point.
echo "== Replaying arm M1 =="
M1_BASE=http://127.0.0.1:9999/v1 M2_BASE=http://127.0.0.1:9999/v1 \
M1_MODEL=mock-m1 M2_MODEL=mock-m2 \
python3 "$HARNESS/replay.py" --arm M1 --k 5 --k-optout 20

echo "== Replaying arm M2 =="
M1_BASE=http://127.0.0.1:9999/v1 M2_BASE=http://127.0.0.1:9999/v1 \
M1_MODEL=mock-m1 M2_MODEL=mock-m2 \
python3 "$HARNESS/replay.py" --arm M2 --k 5 --k-optout 20

echo "== Analysis =="
python3 "$HARNESS/analyze.py" | tee out/analyze_stdout.txt
echo "== Extra metrics (bootstrap CI) =="
python3 "$HARNESS/metrics_extra.py" | tee out/metrics_extra.txt

echo
echo "== Done. Files produced in $(pwd)/out =="
ls -l out
