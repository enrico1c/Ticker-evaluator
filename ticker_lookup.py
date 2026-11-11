"""Offline ticker lookup: python ticker_lookup.py AAPL [BTC EURUSD ...]  (no args = interactive). No network, reads tickers.csv."""
import csv, sys
from pathlib import Path
import math
import re
import sys
from statistics import NormalDist

import pandas as pd
import yfinance as yf
import numpy as np


DB = {r["ticker"]: r for r in csv.DictReader(open(Path(__file__).with_name("tickers.csv"), newline=""))}

def lookup(t):
    """Return (ticker, name, type, exchange) or None. Tries common Yahoo suffixes if the bare input misses."""
    t = t.strip().upper().replace(".", "-")
    for cand in (t, t + "-USD", t + "=X", t + "USD=X", t + "=F", "^" + t):
        if cand in DB:
            r = DB[cand]
            return r["ticker"], r["name"], r["type"], r["exchange"]

def show(t):
    r = lookup(t)
    print(" | ".join(r) if r else f"{t}: not found")

if __name__ == "__main__":
    if sys.argv[1:]:
        for t in sys.argv[1:]: show(t)
    else:
        while (t := input("ticker> ").strip()): show(t)

