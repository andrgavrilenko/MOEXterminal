"""Tab: Арбитраж — 8 sub-tabs covering all arbitrage strategies."""

from __future__ import annotations

import streamlit as st

from ..models import MarketSnapshot
from ..services.arbitrage_service import ArbitrageService
from ..services.funding_service import FundingService
from ._styling import (
    _cols,
    bg_action,
    bg_rate,
    bg_sign,
    number,
    pct,
    price,
)

_arb_svc = ArbitrageService()
_funding_svc = FundingService()


def render_tab_arbitrage(snapshot: MarketSnapshot) -> None:
    tabs = st.tabs([
        "Cash-and-Carry",
        "Reverse C&C",
        "Calendar FX",
        "Cross-Instrument",
        "Cross-FX",
        "Cross-Gold",
        "CIP Arb",
        "Funding",
    ])

    with tabs[0]:
        _render_cash_and_carry(snapshot)
    with tabs[1]:
        _render_reverse_cc(snapshot)
    with tabs[2]:
        _render_calendar_fx(snapshot)
    with tabs[3]:
        _render_cross_instrument(snapshot)
    with tabs[4]:
        _render_cross_fx(snapshot)
    with tabs[5]:
        _render_cross_gold(snapshot)
    with tabs[6]:
        _render_cip(snapshot)
    with tabs[7]:
        _render_funding(snapshot)


# ---- Cash-and-Carry --------------------------------------------------------

def _render_cash_and_carry(snapshot: MarketSnapshot) -> None:
    st.subheader("Cash-and-Carry")
    st.caption("Лонг спот + шорт фьючерс. Implied Rate > КС ЦБ = прибыльная стратегия")

    df = _arb_svc.get_cash_and_carry(snapshot)
    if df.empty:
        st.info("Нет данных")
        return

    st.download_button("CSV", df.to_csv(index=False), "cash_and_carry.csv", "text/csv")

    rate_cols = _cols(df, ["Implied Rate", "Премия к КС", "Премия к RUSFAR"])

    styler = (
        df.style
        .format({c: pct() for c in rate_cols})
        .format({"Спот": price(4), "Фьюч": price(4), "Базис": price(4)})
        .map(bg_rate, subset=rate_cols)
    )
    st.dataframe(styler, width="stretch", hide_index=True)


# ---- Reverse Cash-and-Carry ------------------------------------------------

def _render_reverse_cc(snapshot: MarketSnapshot) -> None:
    st.subheader("Reverse Cash-and-Carry")
    st.caption("Шорт спот + лонг фьючерс. Выгодно при бэквордации (Implied < RUSFAR)")

    df = _arb_svc.get_reverse_cc(snapshot)
    if df.empty:
        st.success("Нет активных Reverse C&C возможностей (все implied >= КС)")
        return

    st.download_button("CSV", df.to_csv(index=False), "reverse_cc.csv", "text/csv")

    cols_show = ["Актив", "Контракт", "Дней", "Спот", "Фьюч",
                 "Implied Rate", "Премия к КС", "Potential Profit"]
    display = df[[c for c in cols_show if c in df.columns]].copy()

    rate_cols = _cols(display, ["Implied Rate", "Премия к КС", "Potential Profit"])

    styler = (
        display.style
        .format({c: pct() for c in rate_cols})
        .format({"Спот": price(4), "Фьюч": price(4)})
        .map(bg_rate, subset=rate_cols)
    )
    st.dataframe(styler, width="stretch", hide_index=True)


# ---- Calendar FX -----------------------------------------------------------

def _render_calendar_fx(snapshot: MarketSnapshot) -> None:
    st.subheader("Calendar FX")
    st.caption("Спред implied rate между ближним и дальним контрактом одного актива")

    cal_df = _arb_svc.get_calendar_fx(snapshot)
    if cal_df.empty:
        st.info("Недостаточно контрактов для календарного спреда")
        return

    rate_cols = _cols(cal_df, ["Fwd Rate", "Rate Diff"])
    styler = (
        cal_df.style
        .format({c: pct() for c in rate_cols})
        .map(bg_rate, subset=rate_cols)
    )
    st.dataframe(styler, width="stretch", hide_index=True)


# ---- Cross-Instrument -----------------------------------------------------

def _render_cross_instrument(snapshot: MarketSnapshot) -> None:
    from ._styling import bg_deviation

    st.subheader("Cross-Instrument")
    st.caption(
        "Сравнение фьючерсов на один базовый актив: "
        "MIX vs MXI (IMOEX), RTS vs RTSM (RTSI). "
        "Spread = price_A / price_B - 1."
    )

    df = _arb_svc.get_cross_instrument(snapshot)
    if df.empty:
        st.info("Нет данных (нужны пары фьючерсов с совпадающими экспирациями)")
        return

    pct_cols = _cols(df, ["Spread", "Rate Diff"])
    pct_cols += [c for c in df.columns if c.startswith("Rate ") and c not in pct_cols]
    price_cols = _cols(df, ["MIX", "MXI", "RTS", "RTSM"])

    styler = (
        df.style
        .format({c: pct() for c in pct_cols})
        .format({c: price(2) for c in price_cols})
        .map(bg_deviation, subset=_cols(df, ["Spread"]))
        .map(bg_rate, subset=_cols(df, ["Rate Diff"]))
    )
    st.dataframe(styler, width="stretch", hide_index=True)


# ---- Cross-FX (Triangle) ---------------------------------------------------

def _render_cross_fx(snapshot: MarketSnapshot) -> None:
    st.subheader("Cross-FX (Треугольный арбитраж)")

    result = _arb_svc.get_cross_fx(snapshot)
    if result is None:
        st.info("Нет спотовых данных для валют")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Si Parity (USDRUB)", f"{result.fair_si:.4f}",
                   delta=f"{result.si_deviation_pct:+.3f}%")
        st.caption(f"Факт: {result.actual_si:.4f}")
    with col2:
        st.metric("Eu Parity (EURRUB)", f"{result.fair_eu:.4f}",
                   delta=f"{result.eu_deviation_pct:+.3f}%")
        st.caption(f"Факт: {result.actual_eu:.4f}")

    st.markdown("---")
    st.caption("Если отклонение значительно (> 0.1%) — возможен треугольный арбитраж")


# ---- Cross-Gold -----------------------------------------------------------

def _render_cross_gold(snapshot: MarketSnapshot) -> None:
    from ._styling import bg_deviation

    st.subheader("Cross-Gold (GD vs GL)")
    st.caption(
        "Сравнение GD (золото в USD) и GL (золото в RUB) одной экспирации. "
        "GL_fair = GD * USDRUB / 31.1035. "
        "Deviation показывает отклонение рыночной цены GL от справедливой."
    )

    df = _arb_svc.get_cross_gold(snapshot)
    if df.empty:
        st.info("Нет данных (нужны GD и GL фьючерсы с совпадающими экспирациями + USDRUB спот)")
        return

    styler = (
        df.style
        .format({"GD (USD)": price(2), "GL (RUB)": price(2),
                 "USDRUB": price(4), "GL Fair": price(2),
                 "Deviation": pct(3)})
        .map(bg_deviation, subset=_cols(df, ["Deviation"]))
    )
    st.dataframe(styler, width="stretch", hide_index=True)

    raw_devs = df["Deviation"].dropna()
    if not raw_devs.empty:
        max_dev = raw_devs.abs().max()
        if max_dev > 0.005:
            st.warning(
                f"Максимальное отклонение {max_dev * 100:.3f}% > 0.5% — "
                "возможна арбитражная возможность GD vs GL."
            )


# ---- CIP Arb ---------------------------------------------------------------

def _render_cip(snapshot: MarketSnapshot) -> None:
    st.subheader("CIP Arb (Covered Interest Parity)")
    st.caption("Implied USDCNY = Si / CR. Forward Premium должен быть стабилен.")

    df = _arb_svc.get_cip(snapshot)
    if df.empty:
        st.info("Нет данных (нужны Si и CR фьючерсы с совпадающими экспирациями)")
        return

    st.download_button("CSV", df.to_csv(index=False), "cip_arb.csv", "text/csv")

    styler = (
        df.style
        .format({"Impl. USDCNY": price(4), "Spot USDCNY": price(4),
                 "Fwd Premium": pct(), "Si (USDRUB)": price(4), "CR (CNYRUB)": price(4)})
        .map(bg_rate, subset=_cols(df, ["Fwd Premium"]))
    )
    st.dataframe(styler, width="stretch", hide_index=True)


# ---- Funding Analysis -------------------------------------------------------

@st.cache_data(ttl=60)
def _get_funding_table(snapshot: MarketSnapshot) -> pd.DataFrame:
    return _funding_svc.get_table(snapshot)


def _render_funding(snapshot: MarketSnapshot) -> None:
    st.subheader("Funding Analysis (Perpetual FX)")
    st.caption("Дневной фандинг вечных валютных фьючерсов vs cash rate")

    df = _get_funding_table(snapshot)

    if df.empty:
        st.info("Нет данных по вечным фьючерсам (USDRUBF, EURRUBF, CNYRUBF)")
        return

    st.download_button("CSV", df.to_csv(index=False), "funding.csv", "text/csv")

    num_cols = _cols(df, ["D", "L1", "L2", "Funding"])
    rate_cols = _cols(df, ["Funding Ann.", "Implied Rate", "Cash Rate",
                           "Funding vs Cash", "Implied vs Cash"])

    styler = (
        df.style
        .format({"Spot": price(4), "Perp": price(4)})
        .format({c: number(6) for c in num_cols})
        .format({c: pct() for c in rate_cols})
        .map(bg_rate, subset=_cols(df, ["Funding Ann.", "Funding vs Cash", "Implied vs Cash"]))
        .map(bg_action, subset=_cols(df, ["Action"]))
        .map(bg_sign, subset=_cols(df, ["Predicted"]))
    )
    st.dataframe(styler, width="stretch", hide_index=True)
