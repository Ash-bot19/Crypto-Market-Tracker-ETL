# Crypto-Market-Tracker-ETL

## Setup
- Create the virtual environment: `python -m venv .venv`
- Activate it (PowerShell): `.\.venv\Scripts\Activate.ps1`
- Install dependencies: `python -m pip install -r requirements.txt`

## CoinGecko Integration
- Uses `pycoingecko` to call the public CoinGecko API (no API key required).
- Quick examples (run inside the virtualenv):
  ```powershell
  .\.venv\Scripts\python.exe -c "from pycoingecko import CoinGeckoAPI; cg = CoinGeckoAPI(); print(cg.get_price(ids='bitcoin', vs_currencies='usd'))"
  ```
- Run the incremental pipeline: `.\.venv\Scripts\python.exe src\etl.py`

## Database Configuration
- Provide a Postgres connection string via `SUPABASE_DATABASE_URL` (e.g. `postgres://user:pass@host:6543/db`).
- If you prefer discrete variables, supply `DB_HOST`, `DB_USER`, `DB_PASSWORD`, optional `DB_NAME`, and `DB_PORT`.
