"""Tests for FundingService — uses synthetic snapshot fixture (no network)."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from moex_dashboard.models import FuturesContract, MarketSnapshot, SpotQuote
from moex_dashboard.services.funding_service import FundingResult, FundingService


@pytest.fixture
def snapshot():
    spots = {
        "USD000UTSTOM": SpotQuote(secid="USD000UTSTOM", name="USDRUB", price=85.0),
        "EUR_RUB__TOM": SpotQuote(secid="EUR_RUB__TOM", name="EURRUB", price=92.0),
        "CNYRUB_TOM": SpotQuote(secid="CNYRUB_TOM", name="CNYRUB", price=11.5),
    }
    futures = {
        "Si": [FuturesContract(secid="SiH6", asset_code="Si",
                               expiry_date=date(2026, 3, 20),
                               price=86.5, days_to_expiry=30)],
        "Eu": [FuturesContract(secid="EuH6", asset_code="Eu",
                               expiry_date=date(2026, 3, 20),
                               price=93.5, days_to_expiry=30)],
        "CR": [FuturesContract(secid="CRH6", asset_code="CR",
                               expiry_date=date(2026, 3, 20),
                               price=11.6, days_to_expiry=30)],
    }
    return MarketSnapshot(
        timestamp=datetime(2026, 3, 16, 12, 0),
        spots=spots,
        futures=futures,
        rusfar=0.15,
        key_rate=0.21,
    )


@pytest.fixture
def svc():
    return FundingService()


def _make_candles(n: int, base_price: float) -> pd.DataFrame:
    """Synthetic minute candles for testing."""
    idx = pd.date_range("2026-03-16 10:00", periods=n, freq="min")
    return pd.DataFrame({"begin": idx, "close": [base_price] * n})


class TestFundingResultModel:
    def test_defaults(self):
        r = FundingResult(name="USDRUB")
        assert r.action == "NEUTRAL"
        assert r.quality == "insufficient"
        assert r.funding is None

    def test_full_result(self):
        r = FundingResult(
            name="USDRUB", spot=85.0, perp=85.1, d=0.05,
            quality="full", l1=0.0085, l2=0.085,
            funding=0.041, funding_ann=0.176,
            predicted="+fund", action="SHORT",
            implied_rate=0.175, cash_rate=0.15,
            funding_vs_cash=0.026, implied_vs_cash=0.025,
        )
        assert r.action == "SHORT"
        assert r.funding_ann == pytest.approx(0.176)


class TestFundingServiceGetResults:
    def test_returns_results_when_no_candles(self, svc, snapshot):
        """With empty candles, all results should have quality=insufficient."""
        empty_df = pd.DataFrame(columns=["begin", "close"])
        candles = {
            "USDRUBF": {"perp": empty_df, "spot": empty_df},
            "EURRUBF": {"perp": empty_df, "spot": empty_df},
            "CNYRUBF": {"perp": empty_df, "spot": empty_df},
        }
        with patch.object(svc, "_load_candles", return_value=candles), \
             patch("moex_dashboard.services.funding_service.load_perpetual_prices",
                   return_value={"USDRUBF": 85.1, "EURRUBF": 92.1, "CNYRUBF": 11.51}), \
             patch("moex_dashboard.services.funding_service.load_perpetual_specs",
                   return_value={"USDRUBF": {"k1": 0.0001, "k2": 0.001},
                                 "EURRUBF": {"k1": 0.0001, "k2": 0.001},
                                 "CNYRUBF": {"k1": 0.0001, "k2": 0.001}}):
            results = svc.get_results(snapshot)

        assert len(results) == 3
        for r in results:
            assert r.quality == "insufficient"
            assert r.action == "NEUTRAL"

    def test_returns_results_with_candles(self, svc, snapshot):
        """With sufficient candles, funding should be calculated."""
        perp_c = _make_candles(250, 85100.0)  # raw price before divisor
        spot_c = _make_candles(250, 85.0)

        candles = {
            "USDRUBF": {"perp": perp_c, "spot": spot_c},
            "EURRUBF": {"perp": pd.DataFrame(columns=["begin", "close"]),
                        "spot": pd.DataFrame(columns=["begin", "close"])},
            "CNYRUBF": {"perp": pd.DataFrame(columns=["begin", "close"]),
                        "spot": pd.DataFrame(columns=["begin", "close"])},
        }
        with patch.object(svc, "_load_candles", return_value=candles), \
             patch("moex_dashboard.services.funding_service.load_perpetual_prices",
                   return_value={"USDRUBF": 85.1}), \
             patch("moex_dashboard.services.funding_service.load_perpetual_specs",
                   return_value={"USDRUBF": {"k1": 0.0001, "k2": 0.001}}):
            results = svc.get_results(snapshot)

        usdrub = next((r for r in results if r.name == "USDRUB"), None)
        assert usdrub is not None
        assert usdrub.spot == 85.0
        # D = avg(85100/1000 - 85.0) = avg(0.1) = 0.1, which is > L2 → funding is capped
        assert usdrub.funding is not None

    def test_implied_rate_from_futures(self, svc, snapshot):
        """FundingService should derive implied_rate from dated futures."""
        empty_df = pd.DataFrame(columns=["begin", "close"])
        candles = {
            "USDRUBF": {"perp": empty_df, "spot": empty_df},
            "EURRUBF": {"perp": empty_df, "spot": empty_df},
            "CNYRUBF": {"perp": empty_df, "spot": empty_df},
        }
        with patch.object(svc, "_load_candles", return_value=candles), \
             patch("moex_dashboard.services.funding_service.load_perpetual_prices",
                   return_value={"USDRUBF": 85.1}), \
             patch("moex_dashboard.services.funding_service.load_perpetual_specs",
                   return_value={"USDRUBF": {"k1": 0.0001, "k2": 0.001}}):
            results = svc.get_results(snapshot)

        usdrub = next((r for r in results if r.name == "USDRUB"), None)
        assert usdrub is not None
        # implied_rate = (86.5/85.0 - 1) * 365/30 ≈ 0.215
        assert usdrub.implied_rate is not None
        assert usdrub.implied_rate == pytest.approx(0.215, rel=0.05)


class TestFundingServiceSignals:
    def test_get_signals_filters_neutral(self, svc, snapshot):
        mock_results = [
            FundingResult(name="USDRUB", action="SHORT"),
            FundingResult(name="EURRUB", action="NEUTRAL"),
            FundingResult(name="CNYRUB", action="LONG"),
        ]
        with patch.object(svc, "get_results", return_value=mock_results):
            signals = svc.get_signals(snapshot)

        assert len(signals) == 2
        assert all(s.action != "NEUTRAL" for s in signals)
