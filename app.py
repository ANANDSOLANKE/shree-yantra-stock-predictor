from flask import Flask, request, jsonify, send_file, abort
import yfinance as yf
import requests
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_PATH = os.path.join(STATIC_DIR, "index.html")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

EXCHANGE_PRIORITY = [
    "NSE", "BSE",
    "NYQ", "NMS", "ASE", "PCX", "BATS",
    "LSE",
    "TOR", "VAN",
    "ASX",
    "JPX", "TSE", "OSE",
    "HKG",
    "SES",
    "KSC", "KOSDAQ",
    "SHH", "SHZ",
    "EPA", "ETR", "FRA", "BIT", "AMS", "BRU", "VIE", "STO", "HEL", "COP", "ICE", "MCE",
    "SAO",
    "JNB",
    "MEX",
    "DFM", "ADX",
]

def yahoo_search(query: str, count: int = 10):
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    r = requests.get(url, params={"q": query, "quotesCount": count, "newsCount": 0}, timeout=8)
    r.raise_for_status()
    data = r.json()
    quotes = data.get("quotes", []) or []
    items = []
    for q in quotes:
        if q.get("quoteType") not in ("EQUITY", "ETF", "MUTUALFUND", "INDEX", "CURRENCY"):
            continue
        items.append({
            "symbol": q.get("symbol"),
            "shortname": q.get("shortname") or q.get("longname") or q.get("longName") or "",
            "exchange": q.get("exchange") or q.get("exchDisp") or "",
            "type": q.get("quoteType", ""),
        })
    return items

def resolve_symbol(query_or_symbol: str):
    q = (query_or_symbol or "").strip()
    if not q:
        return None
    try:
        h = yf.Ticker(q).history(period="1d")
        if not h.empty:
            return q.upper()
    except Exception:
        pass
    if "." not in q:
        for suffix in (".NS", ".BO"):
            try_symbol = (q + suffix).upper()
            try:
                h = yf.Ticker(try_symbol).history(period="1d")
                if not h.empty:
                    return try_symbol
            except Exception:
                continue
    try:
        results = yahoo_search(q, count=20)
        if not results:
            return None
        best_score = 10_000
        best_symbol = None
        for it in results:
            ex = it.get("exchange") or ""
            sym = it.get("symbol") or ""
            if not sym:
                continue
            score = EXCHANGE_PRIORITY.index(ex) if ex in EXCHANGE_PRIORITY else 1000
            if score < best_score:
                best_score = score
                best_symbol = sym
        return (best_symbol or results[0]["symbol"]).upper() if results else None
    except Exception:
        return None

@app.route("/")
def index():
    if os.path.exists(INDEX_PATH):
        return send_file(INDEX_PATH)
    return abort(404, description="index.html not found")

@app.route("/stock")
def stock():
    raw_ticker = request.args.get("ticker")
    query = request.args.get("q")
    want = raw_ticker or query
    symbol = resolve_symbol(want)
    if not symbol:
        return jsonify({"error": "Could not resolve symbol from input"}), 404
    try:
        y = yf.Ticker(symbol)
        h = y.history(period="1d")
        if h.empty:
            h = y.history(period="2d")
            if h.empty:
                return jsonify({"error": f"No data found for {symbol}"}), 404
        last = h.iloc[-1]
        return jsonify({
            "ticker": symbol,
            "open": round(float(last["Open"]), 2),
            "high": round(float(last["High"]), 2),
            "low": round(float(last["Low"]), 2),
            "close": round(float(last["Close"]), 2),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/suggest")
def suggest():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"results": []})
    try:
        results = yahoo_search(q, count=10)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"results": [], "error": str(e)}), 500

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
