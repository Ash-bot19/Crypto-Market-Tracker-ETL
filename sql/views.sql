-- sql/views.sql
create or replace view v_latest_prices as
select p.asset_id, a.symbol, a.name, p.price, p.market_cap, p.volume, p.ts
from prices p
join (select asset_id, max(ts) as max_ts from prices group by asset_id) last
  on last.asset_id = p.asset_id and last.max_ts = p.ts
join assets a on a.asset_id = p.asset_id
order by market_cap desc nulls last;

create or replace view v_price_change_24h as
with latest as (select * from v_latest_prices),
p24 as (
  select p.asset_id, p.price as price_24h
  from prices p
  join (
    select asset_id, max(ts) as ts_24h
    from prices
    where ts <= now() at time zone 'utc' - interval '24 hours'
    group by asset_id
  ) t on t.asset_id = p.asset_id and t.ts_24h = p.ts
)
select l.asset_id, l.symbol, l.name, l.price as price_now, p24.price_24h,
       case when p24.price_24h is not null
            then round((l.price - p24.price_24h)/p24.price_24h*100.0, 4)
            else null end as pct_change_24h
from latest l
left join p24 on p24.asset_id = l.asset_id
order by l.market_cap desc nulls last;

create or replace view v_daily_ohlc as
select a.asset_id, a.symbol, a.name,
       d.date, d.open, d.high, d.low, d.close, d.volume, d.market_cap
from daily_metrics d
join assets a on a.asset_id = d.asset_id
order by a.asset_id, d.date desc;

create or replace view v_sparkline_7d as
select p.asset_id, a.symbol, a.name, p.ts, p.price
from prices p
join assets a on a.asset_id = p.asset_id
where p.ts >= now() at time zone 'utc' - interval '7 days'
order by p.asset_id, p.ts;

-- helpful indexes
create index if not exists idx_prices_asset_ts on prices(asset_id, ts desc);
create index if not exists idx_daily_metrics_asset_date on daily_metrics(asset_id, date desc);
