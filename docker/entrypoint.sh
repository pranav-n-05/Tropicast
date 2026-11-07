#!/bin/sh
# Bootstraps data and models on first start, then runs the requested role.
set -e
if [ ! -f data/processed/dataset_manifest.json ]; then
  echo "[entrypoint] no processed data - ingesting IBTrACS"
  tropicast ingest
fi
if [ ! -f artifacts/registry.json ]; then
  echo "[entrypoint] no trained models - training (CPU, several minutes)"
  tropicast train
fi
case "$1" in
  serve)    exec tropicast serve --host 0.0.0.0 --port 8000 ;;
  pipeline) exec tropicast pipeline --interval-min "${PIPELINE_INTERVAL_MIN:-60}" ;;
  *)        exec tropicast "$@" ;;
esac
