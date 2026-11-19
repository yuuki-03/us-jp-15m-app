import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'market.json'
JST = ZoneInfo('Asia/Tokyo')
now = datetime.now(timezone.utc)
result = {'fetched_at': now.isoformat(), 'us': {}, 'intraday': {}, 'errors': {}}
if OUT.exists():
    try:
        old = json.loads(OUT.read_text(encoding='utf-8'))
        for field in ('us', 'intraday'):
            result[field] = old.get(field, {})
    except (ValueError, OSError):
        pass

def valid(v):
    try:
        n = float(v)
        return round(n, 4) if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None

for key, ticker in [('nasdaq', '^IXIC'), ('sox', '^SOX')]:
    try:
        df = yf.Ticker(ticker).history(period='10d', interval='1d', auto_adjust=False)
        rows = [(idx, valid(row['Close'])) for idx, row in df.iterrows()]
        rows = [(idx, close) for idx, close in rows if close is not None]
        if len(rows) < 2:
            raise ValueError('終値が2営業日分取得できません')
        (prev_time, prev), (dt, close) = rows[-2:]
        result['us'][key] = {'close': close, 'change_pct': round((close / prev - 1) * 100, 4), 'date': dt.date().isoformat(), 'fetched_at': now.isoformat()}
    except Exception as exc:
        result['errors'][key] = str(exc)[:200]

for key, ticker in [('nikkei', '^N225'), ('telec', '8035.T'), ('semi', '2644.T')]:
    try:
        df = yf.Ticker(ticker).history(period='5d', interval='15m', auto_adjust=False, prepost=False)
        if df.empty:
            raise ValueError('15分間隔のデータがありません')
        by_day = {}
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime()
            if ts.tzinfo is None:
                raise ValueError('時刻のタイムゾーンが不明です')
            ts = ts.astimezone(JST)
            hhmm = ts.strftime('%H:%M')
            if not ('09:00' <= hhmm < '11:30' or '12:30' <= hhmm < '15:30'):
                continue
            price = valid(row['Close'])
            if price is not None:
                by_day.setdefault(ts.date().isoformat(), []).append({'time': hhmm, 'price': price})
        if not by_day:
            raise ValueError('日本市場の時間帯のデータがありません')
        date = max(by_day)
        result['intraday'][key] = {'date': date, 'points': by_day[date], 'fetched_at': now.isoformat(), 'source_interval': '15m', 'time_meaning': '15分区間の開始時刻'}
    except Exception as exc:
        result['errors'][key] = str(exc)[:200]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('更新:', {k: len(v.get('points', [])) for k, v in result['intraday'].items()}, 'US:', list(result['us']), 'errors:', result['errors'])
if not result['us'] and not result['intraday']:
    raise SystemExit('有効な株価データを一度も取得できませんでした')
