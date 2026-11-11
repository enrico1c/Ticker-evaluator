"""Build/refresh tickers.csv (ticker,name,type,exchange). Re-runnable: merges into the existing file, never drops rows.
Sources: NASDAQ Trader symbol directory (stocks+ETFs, all US exchanges), CoinGecko (crypto), generated FX pairs, curated lists."""
import csv, itertools, json, sys, time, urllib.request
from pathlib import Path

OUT = Path(__file__).with_name("tickers.csv")
NASDAQ = "https://www.nasdaqtrader.com/dynamic/SymDir/"
CRYPTO_PAGES = 8  # 250 coins/page, ranked by market cap; ponytail: raise for deeper coverage (CoinGecko free tier rate-limits)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ticker-builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")

def yahoo(sym):  # BRK.B -> BRK-B, ABC$D -> ABC-PD
    return sym.replace("$", "-P").replace(".", "-")

def us_listings():
    for fname, sym_col, exch_fn in (("nasdaqlisted.txt", "Symbol", lambda r: "NASDAQ"),
                                    ("otherlisted.txt", "ACT Symbol", lambda r: r["Exchange"])):
        lines = [l for l in get(NASDAQ + fname).splitlines() if not l.startswith("File Creation")]
        for r in csv.DictReader(lines, delimiter="|"):
            if r["Test Issue"] == "Y" or not r[sym_col]:
                continue
            yield yahoo(r[sym_col]), r["Security Name"].strip(), "etf" if r["ETF"] == "Y" else "stock", exch_fn(r)

def crypto():
    seen = set()
    for page in range(1, CRYPTO_PAGES + 1):
        try:
            data = json.loads(get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}"))
        except Exception as e:
            print(f"crypto page {page} failed ({e}); keeping what we have", file=sys.stderr); return
        for c in data:
            t = c["symbol"].upper() + "-USD"
            if t not in seen:  # symbols collide; first = highest market cap
                seen.add(t); yield t, c["name"], "crypto", "CCC"
        time.sleep(2.5)

MAJORS = "EUR GBP JPY CHF AUD NZD CAD".split()
OTHERS = ("CNY HKD SGD SEK NOK DKK PLN CZK HUF TRY ZAR MXN BRL INR KRW THB IDR MYR PHP TWD ILS AED SAR "
          "RUB CLP COP ARS PEN EGP NGN KES VND PKR BDT UAH RON BGN ISK").split()

def currencies():
    for a, b in itertools.permutations(["USD"] + MAJORS, 2):
        yield (f"{b}=X" if a == "USD" else f"{a}{b}=X"), f"{a}/{b}", "currency", "CCY"
    for c in OTHERS:
        yield f"{c}=X", f"USD/{c}", "currency", "CCY"
        yield f"{c}USD=X", f"{c}/USD", "currency", "CCY"

COMMODITIES = {  # Yahoo continuous futures
    "GC=F": "Gold", "SI=F": "Silver", "PL=F": "Platinum", "PA=F": "Palladium", "HG=F": "Copper",
    "CL=F": "Crude Oil WTI", "BZ=F": "Brent Crude Oil", "NG=F": "Natural Gas", "HO=F": "Heating Oil",
    "RB=F": "RBOB Gasoline", "ZC=F": "Corn", "ZW=F": "Wheat", "KE=F": "KC HRW Wheat", "ZS=F": "Soybeans",
    "ZM=F": "Soybean Meal", "ZL=F": "Soybean Oil", "ZO=F": "Oats", "ZR=F": "Rough Rice", "KC=F": "Coffee",
    "CC=F": "Cocoa", "SB=F": "Sugar #11", "CT=F": "Cotton", "OJ=F": "Orange Juice", "LBS=F": "Lumber",
    "LE=F": "Live Cattle", "GF=F": "Feeder Cattle", "HE=F": "Lean Hogs", "DC=F": "Class III Milk",
}
BONDS = {  # treasury yields + treasury futures
    "^IRX": "US 13-Week Treasury Yield", "^FVX": "US 5-Year Treasury Yield",
    "^TNX": "US 10-Year Treasury Yield", "^TYX": "US 30-Year Treasury Yield",
    "ZT=F": "2-Year T-Note Futures", "ZF=F": "5-Year T-Note Futures", "ZN=F": "10-Year T-Note Futures",
    "TN=F": "Ultra 10-Year T-Note Futures", "ZB=F": "30-Year T-Bond Futures", "UB=F": "Ultra T-Bond Futures",
}

def curated(d, typ, exch):
    for t, n in d.items():
        yield t, n, typ, exch

def main():
    rows = {}
    if OUT.exists():
        with OUT.open(newline="") as f:
            rows = {r["ticker"]: r for r in csv.DictReader(f)}
    before = len(rows)
    for src in (us_listings, crypto, currencies, lambda: curated(COMMODITIES, "commodity", "CME/NYMEX/COMEX"),
                lambda: curated(BONDS, "bond", "CBOE/CBOT")):
        for t, n, typ, ex in src():
            rows[t] = {"ticker": t, "name": n, "type": typ, "exchange": ex}
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, ["ticker", "name", "type", "exchange"])
        w.writeheader(); w.writerows(sorted(rows.values(), key=lambda r: r["ticker"]))
    print(f"{OUT}: {len(rows)} tickers ({len(rows) - before} new)")

if __name__ == "__main__":
    main()
