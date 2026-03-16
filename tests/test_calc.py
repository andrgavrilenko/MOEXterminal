"""Tests for the calculation layer."""

import pytest

from moex_dashboard.calc.arbitrage import (
    basis,
    carry_premium,
    daily_carry,
    fair_value,
    implied_rate,
)
from moex_dashboard.calc.cip import (
    eu_parity,
    forward_premium,
    implied_usdcny,
    si_parity,
)
from moex_dashboard.calc.stocks import dividend_yield, implied_dividend


# ---- arbitrage.py -----------------------------------------------------------

class TestImpliedRate:
    def test_cnyrub_crh6(self):
        # TZ example: CNYRUB CRH6, spot=11.0935, futures=11.156, days=30
        result = implied_rate(11.156, 11.0935, 30)
        assert result == pytest.approx(0.0685, rel=0.02)

    def test_usdrub_sim6(self):
        # TZ: USDRUB SiM6, spot=76.79, futures=78.60, days=122
        result = implied_rate(78.60, 76.79, 122)
        assert result == pytest.approx(0.0711, rel=0.02)

    def test_zero_days(self):
        assert implied_rate(100, 90, 0) is None

    def test_zero_spot(self):
        assert implied_rate(100, 0, 30) is None

    def test_negative_days(self):
        assert implied_rate(100, 90, -5) is None


class TestFairValue:
    def test_cnyrub(self):
        # TZ: spot=11.0935, rate=0.155, days=30 -> 11.2355
        result = fair_value(11.0935, 0.155, 30)
        assert result == pytest.approx(11.2355, rel=0.01)

    def test_headhunter(self):
        # TZ: spot=2917, rate=0.155, days=31 -> 2955.40
        result = fair_value(2917.0, 0.155, 31)
        assert result == pytest.approx(2955.40, rel=0.01)


class TestCarryPremium:
    def test_negative(self):
        # TZ: implied=0.0662, KS=0.155 -> -0.0888
        result = carry_premium(0.0662, 0.155)
        assert result == pytest.approx(-0.0888, abs=0.001)

    def test_positive(self):
        result = carry_premium(0.175, 0.155)
        assert result == pytest.approx(0.020, abs=0.001)


class TestBasis:
    def test_contango(self):
        assert basis(11.156, 11.0935) == pytest.approx(0.0625, abs=0.001)

    def test_backwardation(self):
        assert basis(76.738, 76.79) < 0


class TestDailyCarry:
    def test_basic(self):
        result = daily_carry(11.156, 11.0935, 30)
        assert result is not None
        assert result == pytest.approx(0.0685, rel=0.02)

    def test_zero_days(self):
        assert daily_carry(100, 90, 0) is None


# ---- cip.py -----------------------------------------------------------------

class TestImpliedUsdcny:
    def test_basic(self):
        # TZ: Si=76.738, CR=11.156 -> 6.8786
        result = implied_usdcny(76.738, 11.156)
        assert result == pytest.approx(6.8786, rel=0.01)

    def test_zero_cr(self):
        assert implied_usdcny(76.738, 0) is None


class TestForwardPremium:
    def test_negative(self):
        # TZ: impl=6.8786, spot=6.9218, days=30 -> approx -7.59%
        result = forward_premium(6.8786, 6.9218, 30)
        assert result is not None
        assert result == pytest.approx(-0.0759, rel=0.05)

    def test_zero_days(self):
        assert forward_premium(6.88, 6.92, 0) is None


class TestSiParity:
    def test_basic(self):
        # TZ: CNYRUB=11.0935, USDCNY=6.9218 -> 76.78
        result = si_parity(11.0935, 6.9218)
        assert result == pytest.approx(76.78, rel=0.01)


class TestEuParity:
    def test_basic(self):
        # TZ: USDRUB=76.79, EURUSD=1.1861 -> 91.08
        result = eu_parity(76.79, 1.1861)
        assert result == pytest.approx(91.08, rel=0.01)


# ---- stocks.py ---------------------------------------------------------------

class TestImpliedDividend:
    def test_headhunter_hdh6(self):
        # TZ: spot=2917, futures=2951, rate=0.155, days=31 -> div=4.40
        result = implied_dividend(2917.0, 2951.0, 0.155, 31)
        assert result == pytest.approx(4.40, rel=0.05)

    def test_headhunter_hdm6(self):
        # TZ: spot=2917, futures=2885, rate=0.155, days=122 -> div=183.12
        result = implied_dividend(2917.0, 2885.0, 0.155, 122)
        assert result == pytest.approx(183.12, rel=0.02)


class TestDividendYield:
    def test_basic(self):
        # 4.40 / 2917 = 0.0015
        result = dividend_yield(4.40, 2917.0)
        assert result == pytest.approx(0.0015, rel=0.05)

    def test_zero_spot(self):
        assert dividend_yield(10, 0) is None
