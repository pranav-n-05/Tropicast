"""Download + process HURSAT-B1 for all RSMC New Delhi storms (1982-2015)."""
import logging
import pandas as pd
from tropicast.ingestion.registry import get
from tropicast.datasets.build import load_tracks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
t = load_tracks("tracks")
sids = set(t.loc[t.agency == "newdelhi", "sid"])
con = get("hursat_b1")
if not con.index_path.exists():
    print("index:", len(con.build_index(sids)))
res = con.fetch(sids, workers=6)
print(res)
