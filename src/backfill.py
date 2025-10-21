# src/backfill.py
import yaml
from datetime import datetime, timezone, timedelta
try:
    from .coingecko import get_market_chart
    from .db import get_conn, upsert_prices
except ImportError as exc:
    if getattr(exc, "name", None) in {"coingecko", "db"}:
        from coingecko import get_market_chart
        from db import get_conn, upsert_prices
    else:
        raise
from time import sleep

def load_assets():
    with open("src/coins.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["assets"]

# CoinGecko limits market_chart to ~90 days per call for 'hourly'; loop in chunks.
def backfill(days=90):
    asset_ids = load_assets()
    rows = []
    for cid in asset_ids:
        # up to 90 days in one go; for longer, just loop (example keeps it simple)
        chart = get_market_chart(cid, days=days, interval="hourly", vs="usd")
        mc_map = {int(t[0]): t[1] for t in chart.get("market_caps", [])}
        vol_map = {int(t[0]): t[1] for t in chart.get("total_volumes", [])}
        for ms, price in chart.get("prices", []):
            ts = datetime.fromtimestamp(ms/1000, tz=timezone.utc).replace(microsecond=0)
            rows.append((cid, ts, price, mc_map.get(int(ms)), vol_map.get(int(ms))))
        sleep(1)  # be kind to CG

    with get_conn() as conn:
        upsert_prices(conn, rows)

if __name__ == "__main__":
    backfill(days=90)
