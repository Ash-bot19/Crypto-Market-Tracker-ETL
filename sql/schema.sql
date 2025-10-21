-- sql/schema.sql

-- 1) reference assets
create table if not exists assets (
  asset_id      text primary key,          -- coingecko id (e.g., 'bitcoin')
  symbol        text not null,             -- 'btc'
  name          text not null,             -- 'Bitcoin'
  first_seen_at timestamptz default now()
);

-- 2) 1-min (or hourly) candles/points (we’ll store “market_chart” snapshots)
--    Use ts as start of bucket (UTC).
create table if not exists prices (
  asset_id    text references assets(asset_id) on delete cascade,
  ts          timestamptz not null,
  price       numeric(20,8) not null,      -- spot price
  market_cap  numeric(30,2),
  volume      numeric(30,2),
  source      text default 'coingecko',
  inserted_at timestamptz default now(),
  primary key (asset_id, ts)
);

-- 3) daily aggregates (optional convenience)
create table if not exists daily_metrics (
  asset_id    text references assets(asset_id) on delete cascade,
  date        date not null,
  open        numeric(20,8),
  high        numeric(20,8),
  low         numeric(20,8),
  close       numeric(20,8),
  volume      numeric(30,2),
  market_cap  numeric(30,2),
  inserted_at timestamptz default now(),
  primary key (asset_id, date)
);

-- Helpful indexes
create index if not exists idx_prices_ts on prices(ts);
create index if not exists idx_daily_metrics_date on daily_metrics(date);

-- If you plan to expose via Supabase REST/RLS:
--   Create a service role key for the ETL (server-side) and separate anon key for clients.
--   Keep ETL using DB password or service role key; DO NOT use anon key in Actions.
