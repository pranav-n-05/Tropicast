"""Command-line entry point: ``tropicast <command>``."""
from __future__ import annotations

import argparse
import json
import logging


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="tropicast", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="fetch IBTrACS (conditional GET) and rebuild processed tables")
    t = sub.add_parser("train", help="train, calibrate, evaluate and register models")
    t.add_argument("--fast", action="store_true", help="small GRU/GBM budget (smoke run)")
    r = sub.add_parser("pipeline", help="real-time pipeline: poll sources, forecast active storms")
    r.add_argument("--once", action="store_true")
    r.add_argument("--interval-min", type=float, default=60.0)
    s = sub.add_parser("serve", help="run API + dashboard")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    sub.add_parser("status", help="print data-source status")
    st = sub.add_parser("satellite", help="HURSAT fetch + satellite CV study + localisation + deploy CNN")
    st.add_argument("--fast", action="store_true")
    st.add_argument("--skip-fetch", action="store_true")
    sub.add_parser("risk-eval", help="verify 72-h landfall probabilities on test seasons")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "ingest":
        from tropicast.datasets.build import build_processed
        print(json.dumps(build_processed(refresh=True), indent=2, default=str))
    elif args.cmd == "train":
        from tropicast.training.pipeline import run
        rep = run(fast=args.fast)
        print(json.dumps(rep["selection"], indent=2))
    elif args.cmd == "pipeline":
        from tropicast.realtime.pipeline import loop, run_once
        print(json.dumps(run_once(), indent=2, default=str)) if args.once else loop(args.interval_min)
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("tropicast.api.app:app", host=args.host, port=args.port)
    elif args.cmd == "satellite":
        from tropicast.datasets.build import load_tracks
        from tropicast.ingestion.registry import get
        from tropicast.satellite import deploy, localization, study
        if not args.skip_fetch:
            t = load_tracks("tracks")
            get("hursat_b1").fetch(set(t.loc[t.agency == "newdelhi", "sid"]))
        r = study.run(fast=args.fast)
        loc = localization.run(epochs=2 if args.fast else 20)
        dep = deploy.train_deploy(members=1 if args.fast else 3, epochs=2 if args.fast else 15)
        print(json.dumps({"estimation": r["estimation"]["common_subset"], "localization": loc, "deploy": dep},
                         indent=2, default=str))
    elif args.cmd == "risk-eval":
        from tropicast.risk.evaluate import run as risk_run
        print(json.dumps(risk_run(), indent=2, default=str))
    elif args.cmd == "status":
        from tropicast.ingestion.registry import all_connectors
        print(json.dumps({k: c.status() for k, c in all_connectors().items()}, indent=2, default=str))


if __name__ == "__main__":
    main()
