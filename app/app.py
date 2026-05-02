import atexit
import csv
import io
import sqlite3
import requests
import yfinance as yf
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, request, render_template, Response

app = Flask(__name__)
DB_PATH = Path(__file__).parent / "nasdaq.db"
DEFAULT_TICKER = "^IXIC"
LOOKBACK_YEARS = 5


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # Delete old DB from previous run
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.commit()
    conn.close()


def cleanup():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Cleaned up {DB_PATH}")


atexit.register(cleanup)


def get_ticker(request) -> str:
    return request.args.get("ticker", DEFAULT_TICKER).strip().upper()


def all_rows(conn, ticker: str):
    return conn.execute(
        "SELECT * FROM daily_prices WHERE ticker = ? ORDER BY date", (ticker,)
    ).fetchall()


def rows_to_lists(rows):
    dates = [r["date"] for r in rows]
    ohlc = [[r["open"], r["close"], r["low"], r["high"]] for r in rows]
    volumes = [[r["close"] >= r["open"], r["volume"]] for r in rows]
    return dates, ohlc, volumes


def aggregate(rows, key_func):
    groups = OrderedDict()
    for r in rows:
        k = key_func(r["date"])
        if k not in groups:
            groups[k] = []
        groups[k].append(r)

    dates, ohlc, volumes = [], [], []
    for k, group in groups.items():
        dates.append(group[0]["date"])
        o = group[0]["open"]
        c = group[-1]["close"]
        h = max(g["high"] for g in group)
        l = min(g["low"] for g in group)
        v = sum(g["volume"] for g in group)
        ohlc.append([o, c, l, h])
        volumes.append([c >= o, v])
    return dates, ohlc, volumes


def fetch_full_ticker(ticker: str) -> int:
    """Fetch 5-year data for a ticker from yfinance and store in DB."""
    end = datetime.now()
    start = end - timedelta(days=LOOKBACK_YEARS * 365)

    yt = yf.Ticker(ticker)
    df = yt.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

    if df.empty:
        raise RuntimeError(f"No data returned for {ticker}")

    conn = get_db()
    rows = []
    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        rows.append((ticker, date_str, float(row["Open"]), float(row["High"]),
                     float(row["Low"]), float(row["Close"]), int(float(row["Volume"]))))

    conn.executemany(
        "INSERT OR REPLACE INTO daily_prices (ticker, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"[init] Fetched {len(rows)} rows for {ticker}")
    return len(rows)


def try_update_ticker(ticker: str) -> int:
    """Check for new trading days (last 10 calendar days) and insert if missing.
    Also trim data older than 5 years from the latest date."""
    end = datetime.now()
    start = end - timedelta(days=10)

    try:
        yt = yf.Ticker(ticker)
        df = yt.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    except Exception:
        return 0

    if df.empty:
        return 0

    conn = get_db()
    new_count = 0
    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        existing = conn.execute(
            "SELECT 1 FROM daily_prices WHERE ticker = ? AND date = ?", (ticker, date_str)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO daily_prices (ticker, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ticker, date_str, float(row["Open"]), float(row["High"]),
                 float(row["Low"]), float(row["Close"]), int(float(row["Volume"])))
            )
            new_count += 1

    if new_count > 0:
        conn.commit()
        # Trim to 5 years
        cutoff = (end - timedelta(days=LOOKBACK_YEARS * 365)).strftime("%Y-%m-%d")
        deleted = conn.execute(
            "DELETE FROM daily_prices WHERE ticker = ? AND date < ?", (ticker, cutoff)
        ).rowcount
        if deleted:
            conn.commit()
        print(f"[update] {ticker}: +{new_count} new, -{deleted} old")

    conn.close()
    return new_count


def ticker_summary(conn, ticker: str):
    latest = conn.execute(
        "SELECT * FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1", (ticker,)
    ).fetchone()
    prev = conn.execute(
        "SELECT * FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1 OFFSET 1", (ticker,)
    ).fetchone()
    date_range = conn.execute(
        "SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM daily_prices WHERE ticker = ?", (ticker,)
    ).fetchone()
    count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM daily_prices WHERE ticker = ?", (ticker,)
    ).fetchone()
    return latest, prev, date_range, count


# ── Indicator calculations (for CSV download) ──

def ma(values, period):
    result = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(round(sum(values[i - period + 1:i + 1]) / period, 4))
    return result


def ema(values, period):
    result = []
    k = 2 / (period + 1)
    prev = None
    for i, v in enumerate(values):
        if i < period - 1:
            result.append(None)
            continue
        if prev is None:
            prev = sum(values[:period]) / period
        else:
            prev = v * k + prev * (1 - k)
        result.append(round(prev, 4))
    return result


def macd(closes, fast=12, slow=26, signal=9):
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    line = [round(f - s, 4) if f is not None and s is not None else None
            for f, s in zip(ema_fast, ema_slow)]
    sig_line = ema([x if x is not None else 0 for x in line], signal)
    # Recalculate properly: ema of non-null macd line values
    sig_line = []
    prev_sig = None
    sk = 2 / (signal + 1)
    for i, v in enumerate(line):
        if v is None:
            sig_line.append(None)
            continue
        if prev_sig is None:
            # Simple average of first 'signal' non-null values
            vals = [line[j] for j in range(i + 1) if line[j] is not None][-signal:]
            prev_sig = sum(vals) / len(vals) if vals else v
        else:
            prev_sig = v * sk + prev_sig * (1 - sk)
        sig_line.append(round(prev_sig, 4))
    hist = [round(line[i] - sig_line[i], 4) if line[i] is not None and sig_line[i] is not None else None
            for i in range(len(line))]
    return line, sig_line, hist


def rsi(closes, period=14):
    result = []
    avg_gain = avg_loss = 0
    for i in range(len(closes)):
        if i < period:
            result.append(None)
            if i > 0:
                change = closes[i] - closes[i - 1]
                if change > 0:
                    avg_gain += change
                else:
                    avg_loss += abs(change)
            if i == period:
                avg_gain /= period
                avg_loss /= period
                rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
                result[-1] = round(100 - 100 / (1 + rs), 2)
            continue
        change = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else float('inf')
        result.append(round(100 - 100 / (1 + rs), 2))
    return result


# ── Download endpoint ──

@app.route("/api/download")
def api_download():
    ticker = get_ticker(request)
    start = request.args.get("start", "")
    end = request.args.get("end", "")

    conn = get_db()
    if start and end:
        rows = conn.execute(
            "SELECT * FROM daily_prices WHERE ticker = ? AND date >= ? AND date <= ? ORDER BY date",
            (ticker, start, end),
        ).fetchall()
    else:
        rows = all_rows(conn, ticker)
    conn.close()

    if not rows:
        return jsonify({"error": "no data"}), 404

    dates = [r["date"] for r in rows]
    opens = [r["open"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    closes = [r["close"] for r in rows]
    volumes = [r["volume"] for r in rows]

    ma5 = ma(closes, 5)
    ma10 = ma(closes, 10)
    ma20 = ma(closes, 20)
    macd_line, macd_signal, macd_hist = macd(closes)
    rsi14 = rsi(closes)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume",
                      "MA5", "MA10", "MA20", "MACD", "Signal", "Histogram", "RSI14"])
    for i in range(len(rows)):
        writer.writerow([
            dates[i],
            f"{opens[i]:.2f}", f"{highs[i]:.2f}", f"{lows[i]:.2f}", f"{closes[i]:.2f}",
            volumes[i],
            f"{ma5[i]:.4f}" if ma5[i] is not None else "",
            f"{ma10[i]:.4f}" if ma10[i] is not None else "",
            f"{ma20[i]:.4f}" if ma20[i] is not None else "",
            f"{macd_line[i]:.4f}" if macd_line[i] is not None else "",
            f"{macd_signal[i]:.4f}" if macd_signal[i] is not None else "",
            f"{macd_hist[i]:.4f}" if macd_hist[i] is not None else "",
            f"{rsi14[i]:.2f}" if rsi14[i] is not None else "",
        ])

    output = buf.getvalue()
    buf.close()

    filename = f"{ticker.replace('^', '')}_{dates[0]}_{dates[-1]}.csv"
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ── Startup: always start fresh ──

init_db()
for tkr in ["^IXIC", "^GSPC", "^DJI"]:
    print(f"[startup] Fetching 5-year history for {tkr}...")
    try:
        fetch_full_ticker(tkr)
    except RuntimeError as e:
        print(f"[startup] WARNING: {e}")


# ── Routes ──

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    ticker = get_ticker(request)
    try_update_ticker(ticker)
    conn = get_db()
    rows = all_rows(conn, ticker)
    conn.close()
    dates, ohlc, volumes = rows_to_lists(rows)
    return jsonify({"ticker": ticker, "dates": dates, "ohlc": ohlc, "volumes": volumes})


@app.route("/api/data/weekly")
def api_data_weekly():
    ticker = get_ticker(request)
    conn = get_db()
    rows = all_rows(conn, ticker)
    conn.close()
    dates, ohlc, volumes = aggregate(
        rows,
        lambda d: d[:4] + "-W" + str(datetime.strptime(d, "%Y-%m-%d").isocalendar()[1]).zfill(2)
    )
    return jsonify({"ticker": ticker, "dates": dates, "ohlc": ohlc, "volumes": volumes})


@app.route("/api/data/monthly")
def api_data_monthly():
    ticker = get_ticker(request)
    conn = get_db()
    rows = all_rows(conn, ticker)
    conn.close()
    dates, ohlc, volumes = aggregate(rows, lambda d: d[:7])
    return jsonify({"ticker": ticker, "dates": dates, "ohlc": ohlc, "volumes": volumes})


@app.route("/api/dates")
def api_dates():
    ticker = get_ticker(request)
    conn = get_db()
    rows = conn.execute(
        "SELECT date FROM daily_prices WHERE ticker = ? ORDER BY date", (ticker,)
    ).fetchall()
    conn.close()
    return jsonify([r["date"] for r in rows])


@app.route("/api/summary")
def api_summary():
    ticker = get_ticker(request)
    conn = get_db()
    latest, prev, date_range, count = ticker_summary(conn, ticker)
    conn.close()

    if not latest:
        return jsonify({"error": "no data"}), 404

    change = latest["close"] - prev["close"] if prev else 0
    change_pct = (change / prev["close"] * 100) if prev else 0

    return jsonify({
        "ticker": ticker,
        "latest_date": latest["date"],
        "latest_close": round(latest["close"], 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "date_min": date_range["min_date"],
        "date_max": date_range["max_date"],
        "total_rows": count["cnt"],
    })


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json()
    if not data or "ticker" not in data:
        return jsonify({"error": "ticker is required"}), 400

    ticker = data["ticker"].strip().upper()

    # Check if already in database
    conn = get_db()
    rows = all_rows(conn, ticker)
    if rows:
        conn.close()
        # Try to get any new data since last fetch
        try_update_ticker(ticker)
        conn = get_db()
        rows = all_rows(conn, ticker)
        conn.close()
        dates, ohlc, volumes = rows_to_lists(rows)
        return jsonify({"ticker": ticker, "dates": dates, "ohlc": ohlc, "volumes": volumes, "source": "db"})
    conn.close()

    # Fetch full history from yfinance
    try:
        fetch_full_ticker(ticker)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404

    conn = get_db()
    rows = all_rows(conn, ticker)
    conn.close()
    dates, ohlc, volumes = rows_to_lists(rows)
    return jsonify({
        "ticker": ticker, "dates": dates, "ohlc": ohlc, "volumes": volumes,
        "source": "yfinance", "rows": len(rows)
    })


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])

    try:
        resp = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 10, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return jsonify([])

    results = []
    for quote in data.get("quotes", []):
        symbol = quote.get("symbol", "")
        name = quote.get("shortname") or quote.get("longname") or ""
        ex = quote.get("exchange", "")
        qtype = quote.get("quoteType", "")
        # Only include equities and ETFs
        if qtype not in ("EQUITY", "ETF"):
            continue
        # Filter out non-US symbols (keep those without dots or with common US patterns)
        if "." in symbol:
            continue
        results.append({
            "symbol": symbol,
            "name": name,
            "exchange": ex,
        })

    return jsonify(results[:8])


@app.route("/api/ticker-info")
def api_ticker_info():
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker required"}), 400
    try:
        yt = yf.Ticker(ticker)
        info = yt.info
        name = info.get("shortName") or info.get("longName") or ticker
        ex = info.get("exchange", "")
    except Exception:
        name, ex = ticker, ""
    return jsonify({"ticker": ticker, "name": name, "exchange": ex})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
