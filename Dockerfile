# CourtVision API image.
# The warehouse is NOT baked in: mount ./data (ingested locally, since
# stats.nba.com blocks datacenter IPs) or set COURTVISION_DEMO=1 to boot
# with a synthetic warehouse.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY scripts ./scripts
COPY tests/synth.py ./scripts/_synth.py
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV COURTVISION_DB=/app/data/courtvision.duckdb \
    COURTVISION_MODELS=/app/data/models

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
