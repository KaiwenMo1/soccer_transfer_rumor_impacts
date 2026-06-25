#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
SOURCE_PRESET="${SOURCE_PRESET:-fast_no_api}"
MAX_RECORDS="${MAX_RECORDS:-20}"
DAYS_BACK="${DAYS_BACK:-21}"
PAUSE="${PAUSE:-0.1}"

START_DATE="$("$PYTHON_BIN" -c 'from datetime import date, timedelta; import os; print((date.today() - timedelta(days=int(os.environ.get("DAYS_BACK", "21")))).isoformat())')"
END_DATE="$("$PYTHON_BIN" -c 'from datetime import date; print(date.today().isoformat())')"

PYTHONPATH=src "$PYTHON_BIN" -m transfer_stock.cli auto-update \
  --start "$START_DATE" \
  --end "$END_DATE" \
  --source-preset "$SOURCE_PRESET" \
  --max-records "$MAX_RECORDS" \
  --pause "$PAUSE" \
  --resume \
  --clubs \
    manchester_united \
    borussia_dortmund \
    juventus \
    lazio \
    ajax \
    sporting_cp \
    fc_porto \
    celtic \
    benfica \
    eagle_football_group \
  --slug local_auto_update \
  --dashboard-output app/static/data/dashboard_data.json
