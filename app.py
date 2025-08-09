from flask import Flask, request, jsonify, send_file, abort
import yfinance as yf
import requests
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_PATH = os.path.join(STATIC_DIR, "index.html")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

EXCHANGE_PRIORITY = [
    "NSE","BSE",
    "NYQ","NMS","ASE","PCX","BATS",
    "LSE",
    "TOR","VAN",
    "ASX",
    "JPX","TSE","OSE",
    "HKG",
    "SES",
    "KSC","KOSDAQ",
    "SHH","SHZ",
    "EPA","ETR","FRA","BIT","AMS","BRU","VIE","STO","HEL","COP","ICE","MCE",
    "SAO","JNB","MEX","DFM","ADX",
]

CACHE = {}
TTL_SUGGEST = 300
TTL_STOCK = 180
TTL_TRENDING = 600

def get_cache(key, ttl):
    now = time.time()
    entry = CACHE.get(key)
    if not entry: return None
    ts, val = entry
    if now - ts > ttl:
        CACHE.pop(key, None)
        return None
    return val

def set_cache(key, val):
    CACHE[key] = (time.time(), val)

def yahoo_search(query: str, count: int = 10):
    q = (query or "").strip().lstrip("$")
    if not q: return []
    ck = f"suggest:{q}:{count}"
    cached = get_cache(ck, TTL_SUGGEST)
    if cached is not None: return cached
    for base in ("https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com"):
        url = f"{base}/v1/finance/search"
        try:
            r = requests.get(url, params={"q": q, "quotesCount": count, "newsCount": 0}, headers=UA, timeout=8)
            r.raise_for_status()
            data = r.json()
            quotes = data.get("quotes", []) or []
            items = []
            for it in quotes:
                if it.get("quoteType") not in ("EQUITY","ETF","MUTUALFUND","INDEX","CURRENCY"):
                    continue
                items.append({
                    "symbol": it.get("symbol"),
                    "shortname": it.get("shortname") or it.get("longname") or it.get("longName") or "",
                    "exchange": it.get("exchange") or it.get("exchDisp") or "",
                    "type": it.get("quoteType",""),
                })
            if items:
                set_cache(ck, items)
                return items
        except Exception:
            continue
    set_cache(ck, [])
    return []

def yahoo_trending(region="US"):
    region = (region or "US").upper()
    ck = f"trending:{region}"
    cached = get_cache(ck, TTL_TRENDING)
    if cached is not None: return cached
    for base in ("https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com"):
        url = f"{base}/v1/finance/trending/{region}"
        try:
            r = requests.get(url, headers=UA, timeout=8)
            r.raise_for_status()
            data = r.json()
            results = data.get("finance", {}).get("result", []) or []
            items = []
            for block in results:
                quotes = (block or {}).get("quotes", []) or []
                for q in quotes:
                    items.append({
                        "symbol": q.get("symbol"),
                        "shortname": q.get("shortName") or q.get("longName") or "",
                    })
            if items:
                set_cache(ck, items[:20])
                return items[:20]
        except Exception:
            continue
    set_cache(ck, [])
    return []

def resolve_symbol(query_or_symbol: str):
    q = (query_or_symbol or "").strip().lstrip("$")
    if not q: return None
    try:
        h = yf.Ticker(q).history(period="1d")
        if not h.empty: return q.upper()
    except Exception:
        pass
    if (" " not in q) and ("." not in q):
        for suffix in (".NS", ".BO"):
            try_symbol = (q + suffix).upper()
            try:
                h = yf.Ticker(try_symbol).history(period="1d")
                if not h.empty: return try_symbol
            except Exception:
                continue
    results = yahoo_search(q, count=20)
    if not results: return None
    best, score = None, 10_000
    for it in results:
        ex = it.get("exchange") or ""
        sym = it.get("symbol") or ""
        if not sym: continue
        s = EXCHANGE_PRIORITY.index(ex) if ex in EXCHANGE_PRIORITY else 1000
        if s < score:
            best, score = sym, s
    return (best or results[0]["symbol"]).upper() if results else None

def get_last_valid_ohlc(symbol: str):
    ck = f"stock:{symbol}"
    cached = get_cache(ck, TTL_STOCK)
    if cached is not None: return cached
    t = yf.Ticker(symbol)
    hist = t.history(period="5d")
    if hist is None or hist.empty:
        hist = t.history(period="1mo")
    if hist is None or hist.empty:
        return None
    hist = hist.dropna(subset=["Open","High","Low","Close"], how="any")
    if hist.empty: return None
    last = hist.iloc[-1]
    data = {
        "open": round(float(last["Open"]), 2),
        "high": round(float(last["High"]), 2),
        "low": round(float(last["Low"]), 2),
        "close": round(float(last["Close"]), 2),
    }
    set_cache(ck, data)
    return data

@app.route("/")
def index():
    if os.path.exists(INDEX_PATH):
        return send_file(INDEX_PATH)
    return abort(404, description="index.html not found")

@app.route("/suggest")
def suggest():
    q = (request.args.get("q") or "").strip()
    if not q: return jsonify({"results": []})
    try:
        results = yahoo_search(q, count=10)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"results": [], "note": f"suggest error: {str(e)}"})

@app.route("/stock")
def stock():
    raw_ticker = request.args.get("ticker")
    query = request.args.get("q")
    want = raw_ticker or query
    symbol = resolve_symbol(want)
    if not symbol:
        return jsonify({"error": "Could not resolve symbol from input"}), 404
    ohlc = get_last_valid_ohlc(symbol)
    if not ohlc:
        return jsonify({"error": f"No price data found for {symbol}"}), 404
    return jsonify({"ticker": symbol, **ohlc})

@app.route("/trending")
def trending():
    reg = (request.args.get("region") or "IN").upper()
    res = yahoo_trending(reg) or yahoo_trending("US")
    return jsonify({"region": reg, "results": res})

@app.route("/debug-paths")
def debug_paths():
    return {
        "BASE_DIR": BASE_DIR,
        "STATIC_DIR": STATIC_DIR,
        "INDEX_PATH": INDEX_PATH,
        "index_exists": os.path.exists(INDEX_PATH),
        "static_list": os.listdir(STATIC_DIR) if os.path.isdir(STATIC_DIR) else "missing",
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
