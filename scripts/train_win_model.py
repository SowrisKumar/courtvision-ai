"""Train the pregame win probability model and print evaluation metrics.

Usage: python scripts/train_win_model.py [test-season]
Trains on every other ingested season; evaluates on the test season
(default: the latest one).
"""

import json
import logging
import sys

from courtvision.config import MODELS_DIR
from courtvision.db.connection import get_connection
from courtvision.metrics.views import build_views
from courtvision.ml.win_probability import train

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    con = get_connection()
    build_views(con)
    meta = train(con, MODELS_DIR, test_season=sys.argv[1] if len(sys.argv) > 1 else None)
    con.close()
    print(json.dumps(meta, indent=2))
