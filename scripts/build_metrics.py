"""Create/refresh the analytics views in the warehouse.

Usage: python scripts/build_metrics.py
"""

import logging

from courtvision.db.connection import get_connection
from courtvision.metrics.views import build_views

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build_metrics")

if __name__ == "__main__":
    con = get_connection()
    for name in build_views(con):
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        log.info("%s: %d rows", name, n)
    con.close()
