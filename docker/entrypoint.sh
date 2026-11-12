#!/bin/sh
# Bootstraps data and models on first start, then runs the requested role.
# If a frozen serving bundle is present (deploy/bundle), start from it instead of
# downloading ~2.5 GB and retraining (small/ephemeral hosts such as Render free).
set -e
if [ ! -f data/processed/dataset_manifest.json ] && [ -d deploy/bundle ]; then
  echo "[entrypoint] restoring frozen serving bundle: $(cat deploy/bundle/BUNDLE.json | tr -d '\n ')"
  cp -R deploy/bundle/data deploy/bundle/artifacts deploy/bundle/reports . 2>/dev/null || true
fi
if [ ! -f data/processed/dataset_manifest.json ]; then
  echo "[entrypoint] no processed data - ingesting IBTrACS"
  tropicast ingest
fi
if [ ! -f artifacts/registry.json ]; then
  echo "[entrypoint] no trained models - training (CPU, several minutes)"
  tropicast train
fi
case "$1" in
  serve)    exec tropicast serve --host 0.0.0.0 --port "${PORT:-8000}" ;;
  pipeline) exec tropicast pipeline --interval-min "${PIPELINE_INTERVAL_MIN:-60}" ;;
  *)        exec tropicast "$@" ;;
esac
