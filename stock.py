import sys
from math import nan
import yfinance as yf

def P(x, *segs):
    #Piecewise-linear score 1-100. segs = (x_from, x_to, score_at_from, score_at_to), ascending x; clamps outside; nan -> 1.
    Bands: good 80-100, medium-good 65-80, medium 45-65, medium-bad 25-45, bad 1-25."
    if x != x: return 1
    for a, b, s, t in segs:
        if x <= b: return s + (t - s) * max(0, (x - a) / (b - a))
    return segs[-1][3]

ND_LIM = {"Technology": 4, "Industrials": 6, "Healthcare": 4, "Consumer Cyclical": 4, "Communication Services": 6,
          "Consumer Defensive": 4, "Energy": 6, "Basic Materials": 4, "Real Estate": 6, "Utilities": 6}  # Financial Services: no filter
MARGIN = {"Technology": (25, 10), "Financial Services": (30, 15), "Industrials": (15, 6), "Healthcare": (20, 8),
          "Consumer Cyclical": (12, 5), "Communication Services": (22, 10), "Consumer Defensive": (10, 4),
          "Energy": (15, 5), "Basic Materials": (18, 8), "Real Estate": (35, 20), "Utilities": (20, 10)}  # (good above, bad below) in %

def row(df, k, i=0):
    try: return float(df.loc[k].iloc[i])
    except Exception: return nan

def run(ticker, name="", exch=""):
    tk = yf.Ticker(ticker); i = tk.info; inc, bal, cf = tk.income_stmt, tk.balance_sheet, tk.cashflow
    sec, f = i.get("sector"), lambda k: float(i.get(k) or nan)
    mcap, ebitda = f("marketCap"), f("ebitda")
    nd = (f("totalDebt") - f("totalCash")) / ebitda if ebitda > 0 else float("inf")
    ie = row(inc, "Interest Expense")
    cover = row(inc, "EBIT") / ie if ie > 0 else float("inf")  # no interest expense = infinitely covered
    print(f"{ticker} {name} [{exch}] sector={sec}")
    if sec in ND_LIM and (nd > ND_LIM[sec] or cover < 2):
        return print(f"EXCLUDED: net debt/EBITDA={nd:.1f} (max {ND_LIM[sec]}), EBIT/interest={cover:.1f} (min 2)")

    rev = inc.loc["Total Revenue"].dropna() if "Total Revenue" in inc.index else []
    cagr = (rev.iloc[0] / rev.iloc[-1]) ** (1 / (len(rev) - 1)) - 1 if len(rev) > 1 else nan  # revenue CAGR, ~4y (yfinance limit)
    roe5 = float((inc.loc["Net Income"] / bal.loc["Stockholders Equity"]).mean()) if "Net Income" in inc.index and "Stockholders Equity" in bal.index else nan
    roic = row(inc, "EBIT") * (1 - row(inc, "Tax Rate For Calcs")) / row(bal, "Invested Capital")
    px = tk.history(period="1y", auto_adjust=True)["Close"].dropna()
    sd = px.pct_change().std() * 252 ** .5
    mom = px.iloc[-1] / px.iloc[-231] - 1 if len(px) > 231 else nan  # ~11 months of trading days
    sy = (abs(row(cf, "Cash Dividends Paid")) + abs(row(cf, "Repurchase Of Capital Stock"))) / mcap
    pe, pb = f("trailingPE"), f("priceToBook")
    pe, pb = pe if pe > 0 else nan, pb if pb > 0 else nan  # negative earnings/equity: not meaningful -> score 1
    eve = f("enterpriseValue") / ebitda if ebitda > 0 else nan
    fcfy, roe, beta = f("freeCashflow") / mcap, f("returnOnEquity"), f("beta")
    hi, lo = MARGIN.get(sec, (20, 8))
    om = f("operatingMargins") * 100
    peg = pe / (cagr * 100) if cagr > 0 else nan

    # ponytail: momentum bands + the caps (x_to of each last "bad"/"good" seg) are invented - spec gives none; edit here
    s_pe = P(pe, (0, 15, 100, 80), (15, 25, 65, 45), (25, 30, 45, 25), (30, 60, 25, 1)) if pe < 30 else \
           P(peg, (0, 1, 100, 80), (1, 2, 65, 45), (2, 4, 25, 1))  # P/E>=30: judged on (P/E)/CAGR
    s_pb = 80 if pb > 4 and roe5 > .25 else P(pb, (0, 1, 100, 80), (1, 3, 65, 45), (3, 4, 45, 25), (4, 8, 25, 1))
    groups = {  # name: (weight, {metric: (weight, value, score 1-100)})
        "valuation": (25, {"PE": (20, pe, s_pe),
                           "EV/EBITDA": (35, eve, P(eve, (0, 8, 100, 80), (8, 14, 65, 45), (14, 15, 45, 25), (15, 30, 25, 1))),
                           "P/B": (10, pb, s_pb),
                           "FCF yield": (35, fcfy, P(fcfy, (0, .02, 1, 25), (.02, .05, 45, 65), (.05, .10, 80, 100)))}),
        "quality": (25, {"ROIC": (35, roic, P(roic, (0, .07, 1, 25), (.07, .08, 25, 45), (.08, .12, 45, 65), (.12, .15, 65, 80), (.15, .30, 80, 100))),
                         "ROE": (20, roe, P(roe, (0, .08, 1, 25), (.08, .15, 45, 65), (.15, .30, 80, 100))),
                         "margins": (20, om, P(om, (0, lo, 1, 25), (lo, hi, 45, 65), (hi, 2 * hi, 80, 100))),
                         "ND/EBITDA": (15, nd, P(nd, (0, 2, 100, 80), (2, 3.5, 65, 45), (3.5, 4, 45, 25), (4, 8, 25, 1))),
                         "EBIT/interest": (10, cover, P(cover, (0, 2, 1, 25), (2, 5, 45, 65), (5, 15, 80, 100)))}),
        "growth": (15, {"CAGR": (100, cagr, P(cagr, (-.10, .03, 1, 25), (.03, .08, 45, 65), (.08, .10, 65, 80), (.10, .25, 80, 100)))}),
        "momentum": (15, {"11m return": (100, mom, P(mom, (-.30, 0, 1, 25), (0, .05, 25, 45), (.05, .20, 45, 65), (.20, .50, 80, 100)))}),
        "risk": (15, {"SD": (50, sd, P(sd, (0, .20, 100, 80), (.20, .35, 65, 45), (.35, .70, 25, 1))),
                      "beta": (50, beta, P(beta, (0, 1, 100, 80), (1, 1.3, 65, 45), (1.3, 2.5, 25, 1)))}),
        "shareholder yield": (5, {"(div+buyback)/mcap": (100, sy, P(sy, (0, .01, 1, 25), (.01, .03, 45, 65), (.03, .08, 80, 100)))}),
    }
    S = round
    total = 0
    for g, (w, ms) in groups.items():
        gs = sum(mw * S(s) for mw, _, s in ms.values()) / 100
        total += w * gs / 100
        print(f"\n{g} ({w}%) -> {gs:.0f}/100")
        for m, (mw, v, s) in ms.items(): print(f"  {m:20} {mw:>3}%  value {v:>9.3f}  score {S(s):>3}/100")
    print(f"\nSCORE {total:.1f}/100")

if __name__ == "__main__":
    assert P(0, (0, 15, 100, 80)) == 100 and P(float("nan"), (0, 1, 1, 2)) == 1 and P(20, (0, 15, 100, 80), (15, 25, 65, 45)) == 55 and P(9, (0, 5, 1, 2)) == 2
    run(*sys.argv[1:2] or ["AAPL"])
