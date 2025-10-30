# Crypto-Market-Tracker-ETL

Python ETL that keeps a Supabase (Postgres) instance in sync with hourly price data from CoinGecko. A scheduled GitHub Actions workflow runs the incremental loader each day, and an optional backfill script can hydrate historical prices on demand.

</div><img width="500" height="300" alt="Crypto_ETL" src="https://github.com/user-attachments/assets/34719813-53f8-4fde-8141-339c5ccf8af2" />



## Architecture
- **Incremental loader (`src/etl.py`)** – Reads the asset list from `src/coins.yaml`, fetches current market metadata plus the last 24 h of hourly candles, and upserts into `assets`, `prices`, and `daily_metrics`.
- **Historical backfill (`src/backfill.py`)** – Reuses the same helpers to pull larger hourly windows (90 days per call) and bulk insert into `prices`.
- **CoinGecko client (`src/coingecko.py`)** – Wraps `pycoingecko.CoinGeckoAPI` with chunking and exponential-backoff (`tenacity`) so rate limits and transient network issues are retried automatically.
- **Database utility (`src/db.py`)** – Accepts a single Postgres connection string (`SUPABASE_DATABASE_URL` or `DATABASE_URL`) or discrete `DB_*` variables. It resolves the hostname to IPv4 (`hostaddr`) which avoids the IPv6 routes that GitHub-hosted runners cannot reach, while still using the hostname for TLS/SNI. Connections are created with `sslmode=require`.
- **SQL folder (`sql/`)** – Holds migration helpers/schema artifacts for the Postgres tables.

## Local Setup
1. **Create and activate a virtual environment**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. **Install dependencies**
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **Configure database credentials**
   - Preferred: set `SUPABASE_DATABASE_URL` (or `DATABASE_URL`) to the Supabase *transaction pooler* endpoint (`postgres://user:pass@host:6543/postgres`).
   - Alternate: export `DB_HOST`, `DB_USER`, `DB_PASSWORD`, optional `DB_NAME`, and `DB_PORT` (default `5432`). IPv4 resolution happens automatically when these are set.

## Running the Pipelines
- **Incremental sync**
  ```powershell
  python -m src.etl
  ```
- **Historical backfill (90 days default)**
  ```powershell
  python -m src.backfill
  ```
  Supply a different window with `python -m src.backfill  # edit days arg in script`.

Environment variables must be set in the shell prior to running these commands.

## GitHub Actions Workflow
- Workflow file: `.github/workflows/etl.yml`
- Triggers: daily at `01:10` UTC and manual `workflow_dispatch`.
- Steps:
  1. Checkout repository.
  2. Install Python 3.11 and project requirements.
  3. Run `python -m src.etl`.
- Secrets:
  - Add `SUPABASE_DATABASE_URL` (or rename in the workflow if you prefer a different key). This should point to the Supabase transaction pooler so connections stay multiplexed and SSL-terminated.
  - Alternatively provide discrete `DB_*` secrets and uncomment the matching lines in the workflow.

If the workflow reports connectivity errors, ensure the secret uses the pooler host (`*.supabase.co` with port `6543`) and that egress access is allowed from GitHub-hosted runners.

## Data Model Reference
| Table            | Key fields                        | Source data                                             |
|------------------|-----------------------------------|---------------------------------------------------------|
| `assets`         | `asset_id`                        | Metadata from `get_coins_markets` (id, symbol, name)    |
| `prices`         | `(asset_id, ts)`                  | Hourly price/market cap/volume from `get_market_chart`  |
| `daily_metrics`  | `(asset_id, date)`                | Daily OHLC + last market cap/volume aggregated locally  |

Modify `src/coins.yaml` to change the tracked asset universe (IDs must match CoinGecko’s slugs).

## Troubleshooting
- **`ModuleNotFoundError: yaml` or similar** – Re-run dependency installation inside the venv (`pip install -r requirements.txt`).
- **`psycopg2.OperationalError` about unreachable IPv6** – Verify you are using the updated codebase and the Supabase URL resolves to a reachable IPv4 address; the helper will inject `hostaddr` automatically when possible.
- **CoinGecko rate limiting** – Calls are retried with exponential backoff up to six attempts. If limits persist, consider reducing the asset list or staggering manual backfills.

## Next Steps
- Add an authenticated CoinGecko/demo API integration if/when credentials become available.
- Extend the workflow with validation queries or alerting once the pipeline is running in production.

## 🚀 Launch the Live Dashboard

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://crypto-market-tracker-etl-t6cymd2ftxylanudhqjlkv.streamlit.app/)
