#!/bin/sh
# Boot sequence: ensure a warehouse exists, refresh views, ensure the win
# probability model exists, then serve the API.
set -e

DB="${COURTVISION_DB:-/app/data/courtvision.duckdb}"
MODELS="${COURTVISION_MODELS:-/app/data/models}"

if [ ! -f "$DB" ]; then
  if [ "$COURTVISION_DEMO" = "1" ]; then
    echo "No warehouse at $DB; COURTVISION_DEMO=1 -> building synthetic demo data"
    python -c "import sys; sys.path.insert(0, '/app/scripts'); from pathlib import Path; from _synth import build_synthetic_db; build_synthetic_db(Path('$DB'))"
  else
    echo "ERROR: no warehouse at $DB."
    echo "Mount a data directory with an ingested courtvision.duckdb (see README),"
    echo "or set COURTVISION_DEMO=1 to boot with synthetic demo data."
    exit 1
  fi
fi

python scripts/build_metrics.py

if [ ! -f "$MODELS/win_probability.joblib" ]; then
  echo "No model artifact found; training win probability model"
  python scripts/train_win_model.py
fi

exec uvicorn courtvision.api.main:app --host 0.0.0.0 --port 8000
