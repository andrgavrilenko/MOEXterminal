"""MOEX Arbitrage Dashboard — Streamlit entry point."""

import time

import streamlit as st

from moex_dashboard.services.market_service import MarketService
from moex_dashboard.ui.sidebar import render_sidebar
from moex_dashboard.ui.tab_arbitrage import render_tab_arbitrage
from moex_dashboard.ui.tab_curves import render_tab_curves
from moex_dashboard.ui.tab_relative import render_tab_relative
from moex_dashboard.ui.tab_stocks import render_tab_stocks

st.set_page_config(page_title="MOEX Arbitrage", layout="wide")
st.title("MOEX Arbitrage Dashboard")


@st.cache_resource
def _get_market_service() -> MarketService:
    return MarketService()


@st.cache_data(ttl=30)
def _get_snapshot():
    svc = _get_market_service()
    return svc.get_snapshot()


snapshot = _get_snapshot()

with st.sidebar:
    render_sidebar(snapshot)
    # Auto-refresh toggle
    auto = st.toggle("Авто-обновление (30с)", value=True)

tab1, tab2, tab3, tab4 = st.tabs(["Арбитраж", "Relative Value", "Кривые", "Акции"])

with tab1:
    render_tab_arbitrage(snapshot)
with tab2:
    render_tab_relative(snapshot)
with tab3:
    render_tab_curves(snapshot)
with tab4:
    render_tab_stocks(snapshot)

# Auto-refresh: sleep then rerun
if auto:
    time.sleep(30)
    st.rerun()
