# src/db.py
import os
import socket
from contextlib import contextmanager
from urllib.parse import urlparse

import psycopg2
from psycopg2 import extensions


def _ipv4_hostaddr(host):
    """Resolve the first IPv4 address for a host (skip IPv6-only results)."""
    if not host:
        return None
    try:
        infos = socket.getaddrinfo(
            host,
            None,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return None

    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET and sockaddr:
            return sockaddr[0]
    return None


def _host_from_dsn(dsn):
    try:
        parts = extensions.parse_dsn(dsn)
        return parts.get("host")
    except (extensions.ProgrammingError, AttributeError):
        return urlparse(dsn).hostname


def conn_kwargs():
    # Prefer a single URL secret when available (Supabase, Heroku, etc.)
    url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        hostaddr = _ipv4_hostaddr(_host_from_dsn(url))
        kwargs = {"dsn": url}
        if hostaddr:
            kwargs["hostaddr"] = hostaddr
        return kwargs

    # Fallback to discrete secrets (host, db, user, pass, port)
    host = os.environ["DB_HOST"]
    kwargs = dict(
        host=host,
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=int(os.environ.get("DB_PORT", "5432")),
    )
    hostaddr = _ipv4_hostaddr(host)
    if hostaddr:
        kwargs["hostaddr"] = hostaddr
    return kwargs


@contextmanager
def get_conn():
    conn = psycopg2.connect(**conn_kwargs(), connect_timeout=10, sslmode="require")
    try:
        yield conn
    finally:
        conn.close()


def upsert_assets(conn, rows):
    with conn, conn.cursor() as cur:
        cur.executemany(
            """
            insert into assets(asset_id, symbol, name)
            values (%s, %s, %s)
            on conflict (asset_id) do update set
              symbol=excluded.symbol,
              name=excluded.name;
            """,
            rows,
        )


def upsert_prices(conn, rows):
    with conn, conn.cursor() as cur:
        cur.executemany(
            """
            insert into prices(asset_id, ts, price, market_cap, volume, source)
            values (%s, %s, %s, %s, %s, 'coingecko')
            on conflict (asset_id, ts) do update set
              price=excluded.price,
              market_cap=excluded.market_cap,
              volume=excluded.volume;
            """,
            rows,
        )


def upsert_daily(conn, rows):
    with conn, conn.cursor() as cur:
        cur.executemany(
            """
            insert into daily_metrics(asset_id, date, open, high, low, close, volume, market_cap)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (asset_id, date) do update set
              open=excluded.open,
              high=excluded.high,
              low=excluded.low,
              close=excluded.close,
              volume=excluded.volume,
              market_cap=excluded.market_cap;
            """,
            rows,
        )
