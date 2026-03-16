"""Tab: Стратегии — Sector Rotation leaderboard + Pref/Ordinary backtest."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from ..services.market_service import MarketService
from ..services.momentum_portfolio_service import MomentumPortfolioService
from ..services.sector_momentum_service import SectorMomentumService
from ._styling import _cols, bg_action, bg_rate, pct, price

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

_market_svc = MarketService(data_dir=_DATA_DIR)
_sector_svc = SectorMomentumService(market_service=_market_svc)
_portfolio_svc = MomentumPortfolioService(market_service=_market_svc)


def render_tab_strategies() -> None:
    sub1, sub2, sub3 = st.tabs(["Сектор Ротация", "Momentum Portfolio", "Преф / Обычка"])
    with sub1:
        _render_sector_rotation()
    with sub2:
        _render_momentum_portfolio()
    with sub3:
        _render_pref_backtest()


# ---------------------------------------------------------------------------
# Sector Rotation
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _get_sector_signals():
    return _sector_svc.get_signals()


def _render_sector_rotation() -> None:
    st.subheader("Сектор Ротация")
    st.caption(
        "Ранжирование 8 отраслевых индексов MOEX по 3-месячному моментуму (m3). "
        "Top-2 → LONG, Bottom-2 → SHORT. Ребалансировка ежемесячно."
    )

    signals = _get_sector_signals()
    if not signals:
        st.info("Нет данных по секторам (snapshot.json)")
        return

    # --- Signal summary banner ---
    longs = [s.name for s in signals if s.signal == "LONG"]
    shorts = [s.name for s in signals if s.signal == "SHORT"]

    col_l, col_s = st.columns(2)
    with col_l:
        st.success(f"**LONG:** {' | '.join(longs)}")
    with col_s:
        st.error(f"**SHORT:** {' | '.join(shorts)}")

    st.markdown("---")

    # --- Leaderboard table ---
    rows = []
    for s in signals:
        rows.append({
            "Ранг": s.rank,
            "Сектор": s.name,
            "Код": s.code,
            "Сигнал": s.signal,
            "Цена": s.price,
            "Δ сег.%": s.today_chg / 100 if s.today_chg is not None else None,
            "m1%": s.m1 / 100 if s.m1 is not None else None,
            "m3%": s.m3 / 100 if s.m3 is not None else None,
            "m6%": s.m6 / 100 if s.m6 is not None else None,
            "m12%": s.m12 / 100 if s.m12 is not None else None,
        })

    df = pd.DataFrame(rows)

    pct_cols = _cols(df, ["Δ сег.%", "m1%", "m3%", "m6%", "m12%"])

    styler = (
        df.style
        .format({"Цена": price(2)})
        .format({c: pct() for c in pct_cols})
        .map(bg_action, subset=_cols(df, ["Сигнал"]))
        .map(bg_rate, subset=_cols(df, ["m3%"]))
        .hide(axis="index")
    )
    st.dataframe(styler, width="stretch", hide_index=True)

    st.caption(f"Данные на дату: {signals[0].date}")


# ---------------------------------------------------------------------------
# Pref / Ordinary backtest
# ---------------------------------------------------------------------------

@st.cache_data
def _load_backtest() -> dict:
    path = _DATA_DIR / "backtest_data.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_PAIR_LABELS = {
    "Portfolio": "Портфель (все пары)",
    "SBER/P": "Сбербанк (SBER / SBERP)",
    "TATN/P": "Татнефть (TATN / TATNP)",
    "RTKM/P": "Ростелеком (RTKM / RTKMP)",
}


def _render_pref_backtest() -> None:
    st.subheader("Преф / Обычка — бэктест")
    st.caption(
        "Парный трейдинг привилегированных vs обычных акций. "
        "Источник: Packman Monitor (статический снимок февраль 2026). "
        "Данные: 2013–2026, недельные бары."
    )

    data = _load_backtest()
    if not data:
        st.info("Файл data/backtest_data.json не найден")
        return

    pair = st.selectbox(
        "Инструмент",
        options=list(_PAIR_LABELS.keys()),
        format_func=lambda k: _PAIR_LABELS[k],
    )

    bt = data.get(pair, {})
    if not bt:
        st.warning(f"Нет данных для {pair}")
        return

    # --- Stats row ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sharpe", f"{bt.get('sharpe', 0):.2f}")
    col2.metric("Альфа годовая", f"{bt.get('alpha_ann', 0):.1f}%")
    col3.metric("Утилизация", f"{bt.get('util', 0):.1f}%")
    col4.metric("Период (лет)", f"{bt.get('yrs', 0):.1f}")

    st.markdown("---")

    # --- Build equity chart ---
    dates = pd.to_datetime(bt.get("d", []))
    strategy = bt.get("s", [])
    benchmark = bt.get("r", [])

    if len(dates) == 0 or len(strategy) == 0:
        st.warning("Нет данных для графика")
        return

    # Normalize to 100 at start
    s0 = strategy[0] if strategy[0] != 0 else 1
    r0 = benchmark[0] if benchmark[0] != 0 else 1

    chart_df = pd.DataFrame({
        "Стратегия": [v / s0 * 100 for v in strategy],
        "Бенчмарк": [v / r0 * 100 for v in benchmark],
    }, index=dates)

    st.line_chart(chart_df, height=400)

    # --- Weekly alpha bar chart (last 52 weeks) ---
    alpha = bt.get("a", [])
    if alpha and len(alpha) == len(dates):
        st.markdown("**Недельная альфа (последние 52 недели)**")
        alpha_df = pd.DataFrame({"Альфа": alpha[-52:]}, index=dates[-52:])
        st.bar_chart(alpha_df, height=200)


# ---------------------------------------------------------------------------
# Momentum Portfolio
# ---------------------------------------------------------------------------

def _render_momentum_portfolio() -> None:
    st.subheader("Momentum Portfolio")
    st.caption(
        "Топ акции внутри LONG-секторов. "
        "Скор = Апсайд% (аналитики) + Рекомендация (buy=30/hold=15/sell=0) + Дивиденд%."
    )

    signals = _get_sector_signals()
    if not signals:
        st.info("Нет данных по секторам")
        return

    longs = [s for s in signals if s.signal == "LONG"]
    if not longs:
        st.info("Нет LONG-секторов в текущих сигналах")
        return

    col_left, col_right = st.columns([2, 1])
    with col_left:
        top_n = st.slider("Топ акций на сектор", min_value=3, max_value=10, value=5)
    with col_right:
        include_flat = st.checkbox("Включить FLAT-секторы", value=False)

    df = _portfolio_svc.get_table(signals, top_n=top_n, include_flat=include_flat)

    if df.empty:
        st.info("Нет данных для отображения (нет пересечения секторов с equity universe)")
        return

    st.download_button("CSV", df.to_csv(index=False), "momentum_portfolio.csv", "text/csv")

    pct_cols = _cols(df, ["Δ%", "Апсайд%", "Дивиденд%"])
    price_cols = _cols(df, ["Цена", "Таргет"])

    def _bg_rec(v):
        if v == "BUY":
            return "background-color: rgba(0, 180, 0, 0.20)"
        if v == "SELL":
            return "background-color: rgba(220, 40, 40, 0.20)"
        return ""

    styler = (
        df.style
        .format({c: price(2) for c in price_cols})
        .format({c: pct() for c in pct_cols})
        .map(bg_rate, subset=_cols(df, ["Апсайд%"]))
        .map(_bg_rec, subset=_cols(df, ["Рек."]))
    )
    st.dataframe(styler, width="stretch", hide_index=True)
