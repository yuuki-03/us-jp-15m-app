import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "history.json"

# 約10年間。2644.Tは上場後のデータのみ使用
END = datetime.now(timezone.utc).date() + timedelta(days=1)
START = END - timedelta(days=3653)

TICKERS = {
    "nasdaq": "^IXIC",
    "sox": "^SOX",
    "nikkei": "^N225",
    "telec": "8035.T",
    "semi": "2644.T",
}


def fetch_daily(ticker):
    df = yf.Ticker(ticker).history(
        start=str(START),
        end=str(END),
        interval="1d",
        auto_adjust=True,
        actions=False,
    )
    if df.empty:
        raise RuntimeError(f"株価データを取得できません: {ticker}")

    closes = {}
    for index, row in df.iterrows():
        price = float(row["Close"])
        if pd.notna(price) and price > 0:
            closes[index.date().isoformat()] = price
    return closes


def changes(closes):
    result = {}
    previous = None
    for date, price in sorted(closes.items()):
        if previous is not None:
            result[date] = round(
                (price / previous - 1) * 100, 4
            )
        previous = price
    return result


def main():
    prices = {
        name: fetch_daily(ticker)
        for name, ticker in TICKERS.items()
    }
    returns = {
        name: changes(series)
        for name, series in prices.items()
    }

    # 日本市場の日付を基準に、直前の米国取引日を探す
    us_dates = sorted(
        set(returns["nasdaq"]) & set(returns["sox"])
    )

    rows = []
    for jp_date in sorted(returns["nikkei"]):
        eligible = [d for d in us_dates if d < jp_date]
        if not eligible:
            continue

        us_date = eligible[-1]

        # 古い米国市場データの誤対応を防止
        if (
            datetime.fromisoformat(jp_date)
            - datetime.fromisoformat(us_date)
        ).days > 5:
            continue

        row = {
            "date": jp_date,
            "us_date": us_date,
            "nasdaq": returns["nasdaq"][us_date],
            "sox": returns["sox"][us_date],
            "nikkei": returns["nikkei"][jp_date],
            "telec": returns["telec"].get(jp_date),
            "semi": returns["semi"].get(jp_date),
        }
        rows.append(row)

    if not rows:
        raise RuntimeError("過去実績データを作成できませんでした")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "start": str(START),
                "end": str(END),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(f"過去実績を{len(rows)}件保存しました")
    print(f"保存先: {OUTPUT}")


if __name__ == "__main__":
    main()
