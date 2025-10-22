import os
import time
from datetime import datetime
from dateutil import tz
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Crypto Market Tracker",
    page_icon="📈",
    layout="wide",
)

# --- Config / Secrets ---
SB_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SB_KEY = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")
DEFAULT_ASSET = st.secrets.get("DEFAULT_ASSET_ID", "bitcoin")

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
}

def sb_rest(path: str, params: dict | None = None):
    assert SB_URL and SB_KEY, "Missing Supabase URL/Key in secrets."
    url = f"{SB_URL}/rest/v1/{path}"
    r = requests.get(url, headers=HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=60)
def load_latest_prices() -> pd.DataFrame:
    data = sb_rest("v_latest_prices", {"select": "*"})
    return pd.DataFrame(data)

@st.cache_data(ttl=60)
def load_changes_24h() -> pd.DataFrame:
    data = sb_rest("v_price_change_24h", {"select": "*"})
    return pd.DataFrame(data)

@st.cache_data(ttl=60)
def load_sparkline(asset_id: str) -> pd.DataFrame:
    data = sb_rest("v_sparkline_7d", {"select": "ts,price", "asset_id": f"eq.{asset_id}"})
    df = pd.DataFrame(data)
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df

@st.cache_data(ttl=300)
def load_ohlc(asset_id: str) -> pd.DataFrame:
    data = sb_rest(
        "v_daily_ohlc",
        {"select": "date,open,high,low,close,volume,market_cap", "asset_id": f"eq.{asset_id}"}
    )
    df = pd.DataFrame(data)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df

def format_currency(x):
    if pd.isna(x): return "—"
    return f"${x:,.2f}" if x >= 1 else f"${x:.3g}"

def format_compact(x):
    if pd.isna(x): return "—"
    return pd.Series([x]).map(lambda n: pd.Series([n]).apply(lambda y: y)).astype(float)  # no-op to stay safe
    # (we'll format inside Plotly; this is placeholder)

def pct_str(x):
    if x is None or pd.isna(x): return "—"
    s = f"{x:+.2f}%"
    return s

# --- UI ---
st.title("📈 Crypto Market Tracker (Streamlit)")

colA, colB = st.columns([1, 3], vertical_alignment="bottom")

with colA:
    st.caption("Data: CoinGecko → GitHub Actions ETL → Supabase Views")
with colB:
    st.caption("Auto-refresh every ~60s; select an asset to explore details.")

# Load data
latest = load_latest_prices()
changes = load_changes_24h()

# Merge for table/KPIs
tbl = None
if not latest.empty:
    tbl = latest.merge(
        changes[["asset_id", "price_now", "pct_change_24h"]].rename(columns={"price_now": "price_now"}),
        on="asset_id",
        how="left"
    )
    # fall back to latest.price if price_now missing
    tbl["display_price"] = tbl["price_now"].fillna(tbl["price"])

# Sidebar
with st.sidebar:
    st.header("Controls")
    search = st.text_input("Search asset", placeholder="btc, eth, solana…").strip().lower()
    asset_options = []
    if tbl is not None:
        asset_options = tbl["asset_id"].tolist()
        # filter options by search
        if search:
            mask = (tbl["name"].str.lower().str.contains(search)) | (tbl["symbol"].str.lower().str.contains(search))
            asset_options = tbl.loc[mask, "asset_id"].tolist()
    default_idx = 0
    if DEFAULT_ASSET in asset_options:
        default_idx = asset_options.index(DEFAULT_ASSET)
    selected_asset = st.selectbox("Asset", options=asset_options or [DEFAULT_ASSET], index=default_idx if asset_options else 0)

# KPIs
k1, k2, k3 = st.columns(3)
if tbl is not None and not tbl.empty:
    tracked_assets = len(tbl)
    top_mc = tbl["market_cap"].dropna().max() if "market_cap" in tbl else None
    avg_24h = tbl["pct_change_24h"].dropna().mean() if "pct_change_24h" in tbl else None

    k1.metric("Tracked Assets", tracked_assets)
    k2.metric("Top Market Cap (Tracked)", format_currency(top_mc if pd.notna(top_mc) else 0))
    k3.metric("Avg 24h Change", f"{avg_24h:+.2f}%" if avg_24h is not None else "—")

# Main layout
left, right = st.columns([2, 1])

# Assets table
with left:
    st.subheader("Assets")
    if tbl is None or tbl.empty:
        st.info("No data yet. Ensure ETL ran and views are created.")
    else:
        view = tbl.copy()
        # filter by search in main table, too
        if search:
            m = (view["name"].str.lower().str.contains(search)) | (view["symbol"].str.lower().str.contains(search))
            view = view[m]
        view = view.sort_values(["market_cap"], ascending=[False], na_position="last")
        view_display = view[[
            "asset_name", "symbol", "display_price", "pct_change_24h", "market_cap", "volume", "ts"
        ]].rename(columns={
            "asset_name":"Asset", "symbol":"Symbol", "display_price":"Price",
            "pct_change_24h":"24h Change", "market_cap":"Market Cap", "volume":"Volume", "ts":"Updated (UTC)"
        })
        # pretty formatting
        if not view_display.empty:
            view_display["Price"] = view_display["Price"].map(format_currency)
            view_display["24h Change"] = view_display["24h Change"].map(pct_str)
            view_display["Market Cap"] = view_display["Market Cap"].map(lambda x: "—" if pd.isna(x) else f"${x:,.0f}")
            view_display["Volume"] = view_display["Volume"].map(lambda x: "—" if pd.isna(x) else f"${x:,.0f}")
            view_display["Updated (UTC)"] = pd.to_datetime(view_display["Updated (UTC)"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            view_display,
            use_container_width=True,
            hide_index=True
        )

# Sparkline
with right:
    st.subheader("7-Day Sparkline")
    if selected_asset:
        spark = load_sparkline(selected_asset)
        if spark.empty:
            st.warning("No sparkline data. Wait for ETL to accumulate hourly points.")
        else:
            fig = px.line(
                spark,
                x="ts", y="price",
                labels={"ts": "Time (UTC)", "price": "Price (USD)"},
            )
            fig.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=280)
            st.plotly_chart(fig, use_container_width=True)

st.subheader("Daily Close")
if selected_asset:
    ohlc = load_ohlc(selected_asset)
    if ohlc.empty:
        st.info("No daily metrics yet. Ensure ETL calculates and upserts daily rows.")
    else:
        fig2 = px.line(
            ohlc,
            x="date", y="close",
            labels={"date":"Date","close":"Close (USD)"},
        )
        fig2.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=420)
        st.plotly_chart(fig2, use_container_width=True)

st.caption("© Your Name — CoinGecko → GitHub Actions → Supabase → Streamlit")
