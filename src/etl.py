# src/etl.py
import yaml, math
from datetime import datetime, timezone, date
from dateutil import tz
from coingecko import get_markets, get_market_chart
from db import get_conn, upsert_assets, upsert_prices, upsert_daily

IST = tz.gettz("Asia/Kolkata")

def load_assets():
    with open("src/coins.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["assets"]

def run_incremental():
    asset_ids = load_assets()

    # 1) assets + latest spot (enrich symbol/name)
    mkt = get_markets(asset_ids, vs="usd")
    asset_rows = []
    for a in mkt:
        asset_rows.append((a["id"], a["symbol"], a["name"]))

    # 2) 1-day chart (hourly) → prices table; also compute daily OHLC
    prices_rows = []
    daily_rows = []

    for cid in asset_ids:
        chart = get_market_chart(cid, days=1, interval="hourly", vs="usd")
        # chart has arrays: prices[[ms, price]], market_caps[[ms, mc]], total_volumes[[ms, vol]]
        mc_map = {int(t[0]): t[1] for t in chart.get("market_caps", [])}
        vol_map = {int(t[0]): t[1] for t in chart.get("total_volumes", [])}

        day_prices = []
        for ms, price in chart.get("prices", []):
            ts = datetime.fromtimestamp(ms/1000, tz=timezone.utc).replace(microsecond=0)
            prices_rows.append((cid, ts, price, mc_map.get(int(ms)), vol_map.get(int(ms))))
            day_prices.append(price)

        if day_prices:
            d = datetime.now(tz=timezone.utc).astimezone(IST).date()
            o, h, l, c = day_prices[0], max(day_prices), min(day_prices), day_prices[-1]
            # use last mc/vol we saw for the day
            last_ms = max(mc_map.keys()) if mc_map else None
            mc = mc_map.get(last_ms) if last_ms else None
            last_ms_v = max(vol_map.keys()) if vol_map else None
            vol = vol_map.get(last_ms_v) if last_ms_v else None
            daily_rows.append((cid, d, o, h, l, c, vol, mc))

    with get_conn() as conn:
        upsert_assets(conn, asset_rows)
        upsert_prices(conn, prices_rows)
        upsert_daily(conn, daily_rows)

if __name__ == "__main__":
    run_incremental()
