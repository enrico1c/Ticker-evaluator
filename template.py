from ticker_lookup import lookup
import yfinance as yf

while t := input("ticker> ").strip():
    r = lookup(t)
    if r is None:
        print("not found"); continue
    ticker, name, typ, exch = r

    if typ == "stock":
        import stock
        stock.run(ticker, name, exch)
    elif typ == "etf":
        etf.run(ticker, name, exch)
    elif typ == "bond":
        bond.run(ticker, name, exch)
    elif typ == "crypto":
        crypto.run(ticker, name, exch)
    elif typ == "currency":
        currency.run(ticker, name, exch)
    elif typ == "commodity":
        commodity.run(ticker, name, exch)
