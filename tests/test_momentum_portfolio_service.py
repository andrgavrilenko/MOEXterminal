"""Tests for MomentumPortfolioService — no network calls."""

from unittest.mock import MagicMock

import pytest

from moex_dashboard.services.market_service import EquityRecord, MarketService
from moex_dashboard.services.momentum_portfolio_service import (
    SECTOR_TICKERS,
    MomentumPortfolioService,
    StockPick,
    _build_pick,
    _rec_label,
)
from moex_dashboard.services.sector_momentum_service import SectorSignal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_signal(code: str, signal: str, m3: float = 5.0) -> SectorSignal:
    return SectorSignal(code=code, name=code, date="2026-01-01", m3=m3, signal=signal, rank=1)


def _make_equity(ticker: str, price: float = 100.0,
                 target: float | None = 130.0,
                 rec: float | None = 1.0,
                 dps: float | None = 5.0) -> EquityRecord:
    return EquityRecord(ticker=ticker, name=ticker, price=price,
                        target=target, rec=rec, dps=dps)


@pytest.fixture
def mock_market_svc():
    """MarketService returning SBER (MOEXFN) and GAZP (MOEXOG)."""
    svc = MagicMock(spec=MarketService)
    svc.get_equities.return_value = [
        _make_equity("SBER", price=300.0, target=390.0, rec=1.0, dps=30.0),
        _make_equity("VTBR", price=80.0,  target=100.0, rec=1.5, dps=4.0),
        _make_equity("GAZP", price=130.0, target=150.0, rec=2.0, dps=0.0),
        _make_equity("LKOH", price=7000.0, target=9000.0, rec=1.0, dps=700.0),
    ]
    return svc


@pytest.fixture
def svc(mock_market_svc):
    return MomentumPortfolioService(market_service=mock_market_svc)


# ---------------------------------------------------------------------------
# SECTOR_TICKERS coverage
# ---------------------------------------------------------------------------

class TestSectorTickers:
    def test_all_8_sectors_present(self):
        from moex_dashboard.services.sector_momentum_service import SECTOR_CODES
        assert set(SECTOR_TICKERS.keys()) == set(SECTOR_CODES)

    def test_no_empty_lists(self):
        for code, tickers in SECTOR_TICKERS.items():
            assert len(tickers) > 0, f"Empty ticker list for {code}"

    def test_no_duplicate_tickers_within_sector(self):
        for code, tickers in SECTOR_TICKERS.items():
            assert len(tickers) == len(set(tickers)), f"Duplicates in {code}"


# ---------------------------------------------------------------------------
# _build_pick
# ---------------------------------------------------------------------------

class TestBuildPick:
    def test_upside_calculated(self):
        eq = _make_equity("SBER", price=300.0, target=390.0, rec=None, dps=None)
        pick = _build_pick("SBER", eq, "MOEXFN")
        assert pick is not None
        assert abs(pick.upside - 30.0) < 0.01

    def test_div_yield_calculated(self):
        eq = _make_equity("SBER", price=300.0, target=None, rec=None, dps=30.0)
        pick = _build_pick("SBER", eq, "MOEXFN")
        assert pick is not None
        assert abs(pick.div_yield - 10.0) < 0.01

    def test_no_data_returns_none(self):
        eq = EquityRecord(ticker="XXX", price=100.0, target=None, rec=None, dps=None)
        assert _build_pick("XXX", eq, "MOEXFN") is None

    def test_score_buy_higher_than_hold(self):
        eq_buy  = _make_equity("A", price=100.0, target=110.0, rec=1.0, dps=0.0)
        eq_hold = _make_equity("B", price=100.0, target=110.0, rec=2.0, dps=0.0)
        pick_buy  = _build_pick("A", eq_buy,  "MOEXFN")
        pick_hold = _build_pick("B", eq_hold, "MOEXFN")
        assert pick_buy.score > pick_hold.score

    def test_no_price_upside_is_none(self):
        eq = EquityRecord(ticker="X", price=None, target=100.0, rec=1.0, dps=None)
        pick = _build_pick("X", eq, "MOEXFN")
        assert pick is not None
        assert pick.upside is None

    def test_div_yield_capped_at_20(self):
        # dps/price = 50% → div_score should be capped at 20
        eq = _make_equity("X", price=100.0, target=None, rec=None, dps=50.0)
        pick = _build_pick("X", eq, "MOEXFN")
        assert pick.score <= 20.0


# ---------------------------------------------------------------------------
# get_picks
# ---------------------------------------------------------------------------

class TestGetPicks:
    def test_only_long_sectors_by_default(self, svc):
        signals = [
            _make_signal("MOEXFN", "LONG"),   # SBER, VTBR
            _make_signal("MOEXOG", "SHORT"),  # GAZP, LKOH — excluded
        ]
        picks = svc.get_picks(signals)
        codes = {p.sector_code for p in picks}
        assert "MOEXFN" in codes
        assert "MOEXOG" not in codes

    def test_include_flat_adds_flat_sectors(self, svc):
        signals = [
            _make_signal("MOEXFN", "LONG"),
            _make_signal("MOEXOG", "FLAT"),
        ]
        picks = svc.get_picks(signals, include_flat=True)
        codes = {p.sector_code for p in picks}
        assert "MOEXOG" in codes

    def test_top_n_respected(self, svc):
        signals = [_make_signal("MOEXFN", "LONG")]
        picks = svc.get_picks(signals, top_n=1)
        assert len(picks) <= 1

    def test_no_long_signals_returns_empty(self, svc):
        signals = [_make_signal("MOEXFN", "SHORT")]
        assert svc.get_picks(signals) == []

    def test_picks_sorted_by_score(self, svc):
        signals = [_make_signal("MOEXFN", "LONG")]
        picks = svc.get_picks(signals, top_n=10)
        scores = [p.score for p in picks]
        assert scores == sorted(scores, reverse=True)

    def test_returns_stock_pick_instances(self, svc):
        signals = [_make_signal("MOEXFN", "LONG")]
        picks = svc.get_picks(signals)
        for p in picks:
            assert isinstance(p, StockPick)

    def test_get_table_has_expected_columns(self, svc):
        signals = [_make_signal("MOEXFN", "LONG")]
        df = svc.get_table(signals)
        assert not df.empty
        for col in ["Сектор", "Тикер", "Апсайд%", "Рек.", "Скор"]:
            assert col in df.columns, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# _rec_label
# ---------------------------------------------------------------------------

class TestRecLabel:
    def test_buy(self):     assert _rec_label(1.0) == "BUY"
    def test_hold(self):    assert _rec_label(2.0) == "HOLD"
    def test_sell(self):    assert _rec_label(3.0) == "SELL"
    def test_none(self):    assert _rec_label(None) == "—"
    def test_fractional_buy(self):  assert _rec_label(1.4) == "BUY"
    def test_fractional_hold(self): assert _rec_label(1.6) == "HOLD"
