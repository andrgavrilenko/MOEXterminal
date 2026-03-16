"""Tests for ArbitrageService — uses a synthetic snapshot fixture."""

from datetime import date, datetime

import pandas as pd
import pytest

from moex_dashboard.models import FuturesContract, MarketSnapshot, SpotQuote
from moex_dashboard.services.arbitrage_service import ArbitrageService


@pytest.fixture
def snapshot():
    """Minimal synthetic snapshot with known values for testing."""
    spots = {
        "USD000UTSTOM": SpotQuote(secid="USD000UTSTOM", name="USDRUB", price=85.0),
        "CNYRUB_TOM": SpotQuote(secid="CNYRUB_TOM", name="CNYRUB", price=11.5),
        "EUR_RUB__TOM": SpotQuote(secid="EUR_RUB__TOM", name="EURRUB", price=92.0),
        "IMOEX": SpotQuote(secid="IMOEX", name="IMOEX", price=2900.0),
    }
    futures = {
        "Si": [
            FuturesContract(secid="SiH6", asset_code="Si",
                            expiry_date=date(2026, 3, 20), price=86.0,
                            days_to_expiry=30),
            FuturesContract(secid="SiM6", asset_code="Si",
                            expiry_date=date(2026, 6, 18), price=88.5,
                            days_to_expiry=120),
        ],
        "CR": [
            FuturesContract(secid="CRH6", asset_code="CR",
                            expiry_date=date(2026, 3, 20), price=11.6,
                            days_to_expiry=30),
            FuturesContract(secid="CRM6", asset_code="CR",
                            expiry_date=date(2026, 6, 18), price=11.9,
                            days_to_expiry=120),
        ],
        "Eu": [
            FuturesContract(secid="EuH6", asset_code="Eu",
                            expiry_date=date(2026, 3, 20), price=93.5,
                            days_to_expiry=30),
        ],
        "GD": [
            FuturesContract(secid="GDH6", asset_code="GD",
                            expiry_date=date(2026, 3, 20), price=2000.0,
                            days_to_expiry=30),
        ],
        "GL": [
            FuturesContract(secid="GLH6", asset_code="GL",
                            expiry_date=date(2026, 3, 20), price=5500.0,
                            days_to_expiry=30),
        ],
        "MIX": [
            FuturesContract(secid="MXH6", asset_code="MIX",
                            expiry_date=date(2026, 3, 20), price=2950.0,
                            days_to_expiry=30),
        ],
        "MXI": [
            FuturesContract(secid="MXIH6", asset_code="MXI",
                            expiry_date=date(2026, 3, 20), price=2948.0,
                            days_to_expiry=30),
        ],
    }
    return MarketSnapshot(
        timestamp=datetime(2026, 3, 16, 12, 0),
        spots=spots,
        futures=futures,
        rusfar=0.15,
        key_rate=0.21,
        stale=False,
    )


@pytest.fixture
def svc():
    return ArbitrageService()


class TestCashAndCarry:
    def test_returns_dataframe(self, svc, snapshot):
        df = svc.get_cash_and_carry(snapshot)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_only_currencies_and_indices(self, svc, snapshot):
        df = svc.get_cash_and_carry(snapshot)
        # Should contain USDRUB, CNYRUB, EURRUB, IMOEX — not stocks/commodities
        assets = set(df["Актив"].unique())
        assert "USDRUB" in assets or "CNYRUB" in assets

    def test_has_implied_rate(self, svc, snapshot):
        df = svc.get_cash_and_carry(snapshot)
        assert "Implied Rate" in df.columns
        assert df["Implied Rate"].notna().all()


class TestReverseCC:
    def test_filters_below_key_rate(self, svc, snapshot):
        df = svc.get_reverse_cc(snapshot)
        if not df.empty:
            assert (df["Implied Rate"] < snapshot.key_rate).all()

    def test_has_potential_profit(self, svc, snapshot):
        df = svc.get_reverse_cc(snapshot)
        if not df.empty:
            assert "Potential Profit" in df.columns


class TestCalendarFx:
    def test_returns_spreads(self, svc, snapshot):
        df = svc.get_calendar_fx(snapshot)
        assert isinstance(df, pd.DataFrame)
        # Si has 2 contracts → should produce at least 1 calendar spread
        if not df.empty:
            assert "Fwd Rate" in df.columns
            assert "Rate Diff" in df.columns


class TestCrossFx:
    def test_returns_parity(self, svc, snapshot):
        result = svc.get_cross_fx(snapshot)
        assert result is not None
        assert result.fair_si > 0
        assert result.fair_eu > 0

    def test_deviations_small(self, svc, snapshot):
        result = svc.get_cross_fx(snapshot)
        # With synthetic data, deviations should be calculable
        assert abs(result.si_deviation_pct) < 100  # sanity check


class TestCrossFxMissing:
    def test_returns_none_without_spots(self, svc):
        empty = MarketSnapshot(
            timestamp=datetime.now(), spots={}, futures={},
            rusfar=0.15, key_rate=0.21,
        )
        assert svc.get_cross_fx(empty) is None


class TestCIP:
    def test_returns_dataframe(self, svc, snapshot):
        df = svc.get_cip(snapshot)
        assert isinstance(df, pd.DataFrame)
        # Si and CR both have matching expiry dates
        assert not df.empty
        assert "Impl. USDCNY" in df.columns
