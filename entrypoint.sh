#!/usr/bin/env bash
#
# The weekly Neotoma DOI minting run, as previously performed by hand:
#
#   uv run ndbdoi.py      # DataCite sandbox pass, used here as a gate
#   uv run ndbdoi.py -m   # the real mint against api.datacite.org
#
# The production mint only runs if the sandbox pass exits clean. Logs from both
# passes are shipped to S3 either way.
#
# Arguments are forwarded to both passes, so the task can be run ad hoc with
# e.g. `-d 66173` to restrict it to specific datasets.

set -uo pipefail

RUN_ID="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
LOG_DIR=/tmp/minting-logs
mkdir -p "$LOG_DIR"

echo "== Neotoma DOI minting run ${RUN_ID} =="
echo "== Gate: DataCite sandbox pass =="
python ndbdoi.py -o "$LOG_DIR/sandbox" "$@"
GATE=$?

if [ "$GATE" -ne 0 ]; then
  echo "Sandbox gate FAILED (exit ${GATE}) — skipping production mint."
  python scripts/ship_logs.py "$LOG_DIR" "${RUN_ID}-gate-failed"
  exit "$GATE"
fi

if [ "${GATE_ONLY:-0}" = "1" ]; then
  echo "GATE_ONLY set — stopping after the sandbox pass."
  python scripts/ship_logs.py "$LOG_DIR" "${RUN_ID}-gate-only"
  exit 0
fi

echo "== Production mint =="
python ndbdoi.py -m -o "$LOG_DIR/mint" "$@"
MINT=$?

python scripts/ship_logs.py "$LOG_DIR" "$RUN_ID"

if [ "$MINT" -ne 0 ]; then
  echo "Production mint reported ${MINT} — see the errored log in S3."
fi
exit "$MINT"
