"""Tests for SectorMomentumService — snapshot mode (no network)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from moex_dashboard.services.market_service import MarketService, SectorInfo
from moex_dashboard.services.sector_momentum_service import (
    SectorMomentumService,
    _assign_signals,
    _momentum,
    _rank_by_m3,
)

import pandas as pd
from datetime import date

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def svc_from_snapshot():
    market_svc = MarketService(data_dir=_DATA_DIR)
    return SectorMomentumService(market_service=market_svc)


@pytest.fixture
def svc_with_mock():
    """Service backed by 8 synthetic sector signals."""
    mock_svc = MagicMock(spec=MarketService)
    mock_svc.get_sectors.return_value = [
        SectorInfo(code="MOEXEU", name="Электроэн.", date="2026-02-19",
                   price=1809.0, m1=0.84, m3=19.75, m6=7.94, m12=-2.12,
                   signal="LONG", today_chg=0.3),
        SectorInfo(code="MOEXOG", name="Нефть и газ", date="2026-02-19",
                   price=4500.0, m1=-1.2, m3=-5.3, m6=-8.0, m12=-15.0,
                   signal="SHORT", today_chg=-0.5),
        SectorInfo(code="MOEXMM", name="Металлы", date="2026-02-19",
                   price=7000.0, m1=3.1, m3=15.2, m6=12.0, m12=8.0,
                   signal="LONG", today_chg=0.8),
        SectorInfo(code="MOEXFN", name="Финансы", date="2026-02-19",
                   price=2100.0, m1=0.5, m3=5.0, m6=3.0, m12=10.0,
                   signal="FLAT", today_chg=0.1),
        SectorInfo(code="MOEXCN", name="Потребит.", date="2026-02-19",
                   price=900.0, m1=1.0, m3=3.0, m6=2.0, m12=5.0,
                   signal="FLAT", today_chg=0.2),
        SectorInfo(code="MOEXTL", name="Телеком", date="2026-02-19",
                   price=1200.0, m1=-0.5, m3=1.0, m6=-1.0, m12=2.0,
                   signal="FLAT", today_chg=-0.1),
        SectorInfo(code="MOEXTN", name="Транспорт", date="2026-02-19",
                   price=1600.0, m1=-2.0, m3=-3.0, m6=-5.0, m12=-8.0,
                   signal="FLAT", today_chg=-0.3),
        SectorInfo(code="MOEXCH", name="Химия", date="2026-02-19",
                   price=1400.0, m1=-3.0, m3=-8.0, m6=-10.0, m12=-12.0,
                   signal="SHORT", today_chg=-0.7),
    ]
    return SectorMomentumService(market_service=mock_svc)


class TestSignalsFromSnapshot:
    def test_returns_8_signals(self, svc_from_snapshot):
        signals = svc_from_snapshot.get_signals()
        assert len(signals) == 8

    def test_all_have_code(self, svc_from_snapshot):
        signals = svc_from_snapshot.get_signals()
        for s in signals:
            assert s.code, "Every signal must have a code"

    def test_signal_values_valid(self, svc_from_snapshot):
        signals = svc_from_snapshot.get_signals()
        valid = {"LONG", "SHORT", "FLAT"}
        for s in signals:
            assert s.signal in valid, f"Bad signal: {s.signal}"

    def test_exactly_2_long(self, svc_from_snapshot):
        signals = svc_from_snapshot.get_signals()
        longs = [s for s in signals if s.signal == "LONG"]
        assert len(longs) == 2

    def test_exactly_2_short(self, svc_from_snapshot):
        signals = svc_from_snapshot.get_signals()
        shorts = [s for s in signals if s.signal == "SHORT"]
        assert len(shorts) == 2

    def test_ranks_contiguous(self, svc_from_snapshot):
        signals = svc_from_snapshot.get_signals()
        ranks = sorted(s.rank for s in signals if s.rank is not None)
        assert ranks == list(range(1, len(ranks) + 1))


class TestSignalsFromMock:
    def test_long_have_highest_m3(self, svc_with_mock):
        signals = svc_with_mock.get_signals()
        longs = [s for s in signals if s.signal == "LONG"]
        shorts = [s for s in signals if s.signal == "SHORT"]
        flats = [s for s in signals if s.signal == "FLAT"]

        min_long_m3 = min(s.m3 for s in longs if s.m3 is not None)
        max_short_m3 = max(s.m3 for s in shorts if s.m3 is not None)
        max_flat_m3 = max(s.m3 for s in flats if s.m3 is not None)

        # LONG m3 > FLAT m3 > SHORT m3
        assert min_long_m3 > max_flat_m3
        assert max_flat_m3 > max_short_m3

    def test_rank1_is_long(self, svc_with_mock):
        signals = svc_with_mock.get_signals()
        rank1 = next(s for s in signals if s.rank == 1)
        assert rank1.signal == "LONG"

    def test_rank8_is_short(self, svc_with_mock):
        signals = svc_with_mock.get_signals()
        rank8 = next(s for s in signals if s.rank == 8)
        assert rank8.signal == "SHORT"


class TestLeaderboard:
    def test_returns_dataframe(self, svc_from_snapshot):
        df = svc_from_snapshot.get_leaderboard()
        assert not df.empty
        assert "signal" in df.columns
        assert "m3" in df.columns

    def test_sorted_by_m3(self, svc_from_snapshot):
        df = svc_from_snapshot.get_leaderboard()
        m3_values = df["m3"].dropna().tolist()
        assert m3_values == sorted(m3_values, reverse=True)


class TestMomentumCalc:
    def test_basic(self):
        # Prices rise from 100 to 464 over the year
        # today = last date, price = 463; 91 days back ≈ 372 → momentum > 0
        idx = pd.date_range("2025-01-01", periods=365, freq="D")
        prices = [100.0 + i for i in range(365)]
        hist = pd.Series(prices, index=idx)
        today = date(2025, 12, 31)  # idx[-1]
        current = 463.0  # roughly today's close
        result = _momentum(current, hist, today, 91)
        assert result is not None
        assert result > 0

    def test_no_history_returns_none(self):
        hist = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
        assert _momentum(100.0, hist, date.today(), 30) is None

    def test_target_before_history(self):
        idx = pd.date_range("2025-06-01", periods=30, freq="D")
        hist = pd.Series([100.0] * 30, index=idx)
        result = _momentum(110.0, hist, date(2025, 6, 30), 365)
        assert result is None  # no data 365 days ago


class TestAssignSignals:
    def test_top2_long_bottom2_short(self):
        from moex_dashboard.services.sector_momentum_service import SectorSignal
        signals = [
            SectorSignal(code=f"S{i}", name=f"S{i}", date="2026-01-01", m3=float(10 - i))
            for i in range(8)
        ]
        result = _assign_signals(signals)
        assert result[0].signal == "LONG"
        assert result[1].signal == "LONG"
        assert result[6].signal == "SHORT"
        assert result[7].signal == "SHORT"
        for s in result[2:6]:
            assert s.signal == "FLAT"
