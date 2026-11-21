import json
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "history.json"

TICKERS = {
    "nasdaq": "^IXIC",
    "sox": "^SOX",
    "nikkei": "^N225",
    "telec": "8035.T",
    "semi": "2644.T",
}
ETF_LISTED = "2021-09-28"


def fetch_daily(name, start, end):
    ticker = TICKERS[name]
    df = yf.Ticker(ticker).history(
        start=str(start),
        end=str(end),
        interval="1d",
        auto_adjust=True,
        actions=False,
    )
    closes = {}
    for index, row in df.iterrows():
        day = index.date().isoformat()
        price = float(row["Close"])
        if isfinite(price) and price > 0 and (name != "semi" or day >= ETF_LISTED):
            closes[day] = price
    if not closes:
        raise RuntimeError(f"No usable daily closes for {ticker}")
    return closes


def changes(closes, sessions, name):
    result = {}
    for previous, current in zip(sessions, sessions[1:]):
        if previous not in closes or current not in closes:
            continue
        value = (closes[current] / closes[previous] - 1) * 100
        # Yahoo has reported an unadjusted jump near the ETF's 2-for-1 split.
        if name == "semi" and "2024-10-07" <= current <= "2024-10-15" and abs(value) >= 40:
            continue
        result[current] = value
    return result


def build_rows(us, jp, returns, start, now):
    us_closes = [us.session_close(day) for day in us.sessions]
    previous_us = None
    rows = []
    for session in jp.sessions:
        if jp.session_close(session) > now:
            break
        position = bisect_left(us_closes, jp.session_open(session)) - 1
        if position < 0 or position == previous_us:
            continue
        previous_us = position
        day = session.date().isoformat()
        us_day = us.sessions[position].date().isoformat()
        if day < str(start) or any(us_day not in returns[key] for key in ("nasdaq", "sox")):
            continue
        rows.append({
            "date": day,
            "us_date": us_day,
            "nasdaq": returns["nasdaq"][us_day],
            "sox": returns["sox"][us_day],
            **{key: returns[key].get(day) for key in ("nikkei", "telec", "semi")},
        })
    return rows


def main():
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("Asia/Tokyo")).date()
    start = (pd.Timestamp(today) - pd.DateOffset(years=10)).date()
    end = today + timedelta(days=1)
    fetch_start = start - timedelta(days=14)
    us = xcals.get_calendar("XNYS", start=fetch_start, end=end)
    jp = xcals.get_calendar("XTKS", start=fetch_start, end=end)

    returns = {}
    for name in TICKERS:
        calendar = us if name in ("nasdaq", "sox") else jp
        sessions = [
            day.date().isoformat() for day in calendar.sessions
            if calendar.session_close(day) <= now
            and (name != "semi" or day.date().isoformat() >= ETF_LISTED)
        ]
        closes = fetch_daily(name, fetch_start, end)
        # Keep the last good history if a fetch is stale or substantially incomplete.
        if sessions[-1] not in closes or sum(day in closes for day in sessions) < 0.99 * len(sessions):
            raise RuntimeError(f"Incomplete daily history for {TICKERS[name]}")
        returns[name] = changes(closes, sessions, name)

    rows = build_rows(us, jp, returns, start, now)
    if not rows:
        raise RuntimeError("No paired market history")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "updated_at": now.isoformat(),
        "start": str(start),
        "end": str(end),
        "rows": rows,
    }, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(f"Saved {len(rows)} historical observations")


if __name__ == "__main__":
    main()
