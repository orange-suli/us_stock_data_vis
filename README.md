# Market Chart

A full-stack financial charting application covering NASDAQ, S&P 500, Dow Jones, and any individual US stock. Interactive candlestick (K-line) charts with MACD, RSI, and moving averages — Flask + SQLite + ECharts.

![python](https://img.shields.io/badge/python-3.12+-blue) ![flask](https://img.shields.io/badge/flask-3.1+-green)

## Features

- **Three major indices** — NASDAQ (^IXIC), S&P 500 (^GSPC), Dow Jones (^DJI) pre-loaded on startup
- **Stock search** — fuzzy autocomplete by ticker or company name (e.g. "san" or "apple")
- **Stock info** — company name + ticker shown below the index dropdown; dropdown auto-switches to the stock's exchange
- **Candlestick chart** with MA5/MA10/MA20, volume, MACD(12,26,9), and RSI(14) sub-panels
- **Daily / Weekly / Monthly** period switching
- **Zoom & pan** — mouse wheel, drag, slider, date search, click any data point, or set a date range and press Enter
- **Hover indicators** — MA, MACD, and RSI values update on mouse move above each panel
- **Intraday chart** — click any data point then "Intraday: YYYY-MM-DD" for 1-minute line chart with MACD/Volume/RSI (last 30 days, free via yfinance)
- **CSV export** — download the visible or custom date range with all indicators
- **Auto-refresh** — fresh 5-year data on every startup; incremental updates while running
- **Self-cleaning** — database wiped on exit; no stale data between sessions

## Quick Start

### Prerequisites

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda

### One-click deploy

**Windows** — double-click `deploy.bat`

**Linux / macOS**:
```bash
bash deploy.sh
```

The script creates the `nasdaq` conda environment, installs dependencies, pulls 5 years of historical data for all three indices, and opens `http://localhost:5000`.

### Desktop EXE (Windows)

On the `desktop-exe` branch:

```bash
# One-click build
build_exe.bat

# Output: dist/MarketChart.exe (~180 MB)
```

Double-click `MarketChart.exe` — no console, browser opens automatically. The app bundles Python, Flask, yfinance, and all templates into a single portable executable.

### Manual setup

```bash
conda create -n nasdaq python=3.12 -y
conda run -n nasdaq pip install -r requirements.txt
conda run -n nasdaq python app/app.py
```

## Project Structure

```
├── deploy.bat              # Web launcher (Windows)
├── deploy.sh               # Web launcher (Linux/macOS)
├── build_exe.bat           # EXE build script (desktop-exe branch)
├── desktop_app.py          # Desktop entry point (desktop-exe branch)
├── requirements.txt        # Python dependencies
├── app/
│   ├── __init__.py
│   ├── app.py              # Flask backend (API + DB + yfinance)
│   └── templates/
│       ├── index.html      # Daily chart (ECharts)
│       └── intraday.html   # Intraday chart (ECharts)
└── README.md
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Chart page |
| `GET` | `/api/summary?ticker=` | Latest price, change, date range |
| `GET` | `/api/data?ticker=` | Daily OHLCV |
| `GET` | `/api/data/weekly?ticker=` | Weekly OHLCV |
| `GET` | `/api/data/monthly?ticker=` | Monthly OHLCV |
| `GET` | `/api/dates?ticker=` | All trading dates |
| `POST` | `/api/fetch` `{"ticker":"AAPL"}` | Fetch & cache stock |
| `GET` | `/api/search?q=` | Autocomplete search (ticker/name) |
| `GET` | `/api/ticker-info?ticker=` | Company name & exchange |
| `GET` | `/api/intraday?ticker=&date=` | 1-minute OHLCV + indicators |
| `GET` | `/api/download?ticker=&start=&end=` | CSV with indicators |

Default ticker is `^IXIC`. All `GET` endpoints accept `?ticker=`.

## CSV Format

`Date, Open, High, Low, Close, Volume, MA5, MA10, MA20, MACD, Signal, Histogram, RSI14`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Charting | ECharts 5.5 |
| Backend | Flask 3.1 |
| Database | SQLite |
| Data source | yfinance |
| Runtime | conda / Python 3.12 |

## License

MIT
