# src/coingecko.py
from datetime import datetime, timedelta, timezone
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pycoingecko import CoinGeckoAPI
from typing import Any

CG_CLIENT = CoinGeckoAPI()

class RateLimit(Exception):
    """Raised when CoinGecko signals the public rate limit."""

def _handle_value_error(err: ValueError) -> None:
    """Inspect CoinGecko's error payload and raise richer exceptions."""
    payload = err.args[0] if err.args else None
    if isinstance(payload, dict):
        status = payload.get("status") or {}
        code = status.get("error_code")
        message = status.get("error_message") or "CoinGecko API error"
        if code == 429:
            raise RateLimit(message) from err
        raise RuntimeError(f"CoinGecko API error {code}: {message}") from err
    raise err

def _call(fn: Any, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as err:
        _handle_value_error(err)
        raise  # pragma: no cover
    except requests.exceptions.RequestException:
        raise
    except Exception as err:
        raise RuntimeError(f"Unexpected CoinGecko client error: {err}") from err

@retry(
    reraise=True,
    retry=retry_if_exception_type((RateLimit, requests.exceptions.RequestException)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(6),
)
def get_markets(ids: list[str], vs="usd"):
    # Chunk ids to respect CoinGecko's per_page limit.
    if not ids:
        return []
    results = []
    for i in range(0, len(ids), 250):
        chunk = ids[i : i + 250]
        params = {
            "vs_currency": vs,
            "ids": chunk,
            "price_change_percentage": ["24h", "7d", "30d"],
            "per_page": len(chunk),
            "page": 1,
            "sparkline": False,
        }
        data = _call(
            CG_CLIENT.get_coins_markets,
            **params,
        )
        results.extend(data)
    return results

@retry(
    reraise=True,
    retry=retry_if_exception_type((RateLimit, requests.exceptions.RequestException)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(6),
)
def get_market_chart(coin_id: str, days: int = 1, interval: str = "hourly", vs="usd"):
    if interval == "hourly":
        fetch_days = max(days, 2)
        data = _call(
            CG_CLIENT.get_coin_market_chart_by_id,
            id=coin_id,
            vs_currency=vs,
            days=fetch_days,
        )
        if fetch_days > days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_ms = int(cutoff.timestamp() * 1000)
            for key in ("prices", "market_caps", "total_volumes"):
                series = data.get(key, [])
                data[key] = [row for row in series if row[0] >= cutoff_ms]
        return data

    params = {"id": coin_id, "vs_currency": vs, "days": days}
    if interval:
        params["interval"] = interval
    return _call(CG_CLIENT.get_coin_market_chart_by_id, **params)
