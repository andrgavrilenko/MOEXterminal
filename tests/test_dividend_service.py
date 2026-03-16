"""Tests for DividendService — no network calls, uses local data files."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from moex_dashboard.services.dividend_service import (
    DividendRecord,
    DividendService,
    _capture_plan,
    _capture_status,
    _classify_tier,
    _parse_record,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------

class TestClassifyTier:
    def test_tier1_at_threshold(self):  assert _classify_tier(0.5)  == 1
    def test_tier1_above(self):         assert _classify_tier(0.75) == 1
    def test_tier1_max(self):           assert _classify_tier(1.0)  == 1
    def test_tier2_at_threshold(self):  assert _classify_tier(0.25) == 2
    def test_tier2_below_tier1(self):   assert _classify_tier(0.49) == 2
    def test_tier0_below_tier2(self):   assert _classify_tier(0.24) == 0
    def test_tier0_zero(self):          assert _classify_tier(0.0)  == 0


# ---------------------------------------------------------------------------
# _parse_record
# ---------------------------------------------------------------------------

class TestParseRecord:
    _REF = date(2026, 3, 16)

    def _raw(self, **kwargs):
        base = {
            "ticker": "SBER",
            "name": "Сбербанк",
            "sector": "Финансы",
            "period": "годовые 2025",
            "div": 30.0,
            "yield": 10.0,
            "price": 300.0,
            "rec_date": "25.06.2026",
            "dsi": 0.6,
        }
        base.update(kwargs)
        return base

    def test_basic_parse(self):
        rec = _parse_record(self._raw(), self._REF, {})
        assert rec is not None
        assert rec.ticker == "SBER"
        assert rec.div == 30.0
        assert rec.tier == 1
        assert rec.rec_date == date(2026, 6, 25)

    def test_ex_date_is_2_days_before_rec(self):
        rec = _parse_record(self._raw(), self._REF, {})
        assert rec.ex_date == date(2026, 6, 23)

    def test_days_to_rec_calculated(self):
        rec = _parse_record(self._raw(rec_date="20.03.2026"), self._REF, {})
        assert rec.days_to_rec == 4

    def test_missing_ticker_returns_none(self):
        assert _parse_record(self._raw(ticker=""), self._REF, {}) is None

    def test_missing_rec_date_returns_none(self):
        assert _parse_record(self._raw(rec_date=""), self._REF, {}) is None

    def test_bad_date_format_returns_none(self):
        assert _parse_record(self._raw(rec_date="2026-06-25"), self._REF, {}) is None

    def test_missing_div_returns_none(self):
        raw = self._raw()
        del raw["div"]
        assert _parse_record(raw, self._REF, {}) is None

    def test_confirmed_when_in_declared(self):
        declared = {
            "SBER": [{"record_date": "2026-06-25", "payment_date": "2026-07-10"}]
        }
        rec = _parse_record(self._raw(), self._REF, declared)
        assert rec.confirmed is True
        assert rec.payment_date == date(2026, 7, 10)

    def test_not_confirmed_when_date_mismatch(self):
        declared = {
            "SBER": [{"record_date": "2026-07-01", "payment_date": "2026-07-15"}]
        }
        rec = _parse_record(self._raw(), self._REF, declared)
        assert rec.confirmed is False

    def test_dsi_zero_is_tier0(self):
        rec = _parse_record(self._raw(dsi=0.1), self._REF, {})
        assert rec.tier == 0


# ---------------------------------------------------------------------------
# DividendService with real data files
# ---------------------------------------------------------------------------

@pytest.fixture
def svc():
    return DividendService(data_dir=_DATA_DIR)


class TestDividendServiceFromFiles:
    def test_returns_list(self, svc):
        records = svc.get_calendar(today=date(2026, 3, 16))
        assert isinstance(records, list)

    def test_all_records_are_dividend_record(self, svc):
        records = svc.get_calendar(today=date(2026, 3, 16))
        for r in records:
            assert isinstance(r, DividendRecord)

    def test_sorted_by_rec_date(self, svc):
        records = svc.get_calendar(today=date(2026, 3, 16))
        dates = [r.rec_date for r in records]
        assert dates == sorted(dates)

    def test_all_dates_in_future(self, svc):
        ref = date(2026, 3, 16)
        records = svc.get_calendar(today=ref)
        for r in records:
            assert r.rec_date >= ref

    def test_days_window_respected(self, svc):
        ref = date(2026, 3, 16)
        records = svc.get_calendar(days=30, today=ref)
        from datetime import timedelta
        cutoff = ref + timedelta(days=30)
        for r in records:
            assert r.rec_date <= cutoff

    def test_min_tier1_filter(self, svc):
        records = svc.get_calendar(min_tier=1, today=date(2026, 3, 16))
        for r in records:
            assert r.tier == 1

    def test_min_tier2_filter(self, svc):
        # min_tier=2 means "include tier 1 and tier 2"
        records = svc.get_calendar(min_tier=2, today=date(2026, 3, 16))
        for r in records:
            assert r.tier in (1, 2)

    def test_get_table_returns_dataframe(self, svc):
        df = svc.get_table(today=date(2026, 3, 16))
        assert not df.empty

    def test_get_table_has_expected_columns(self, svc):
        df = svc.get_table(today=date(2026, 3, 16))
        for col in ["Тир", "Тикер", "Дох.%", "Рек.дата", "Дней до экс", "DSI"]:
            assert col in df.columns

    def test_dias_is_confirmed(self, svc):
        # DIAS is in declared_divs.json with record_date 2026-03-23
        records = svc.get_calendar(today=date(2026, 3, 16))
        dias = next((r for r in records if r.ticker == "DIAS"), None)
        assert dias is not None
        assert dias.confirmed is True

    def test_get_tier1_returns_only_tier1(self, svc):
        records = svc.get_tier1(today=date(2026, 3, 16))
        for r in records:
            assert r.tier == 1


# ---------------------------------------------------------------------------
# _capture_status and _capture_plan
# ---------------------------------------------------------------------------

class TestCaptureStatus:
    def test_watch_far(self):       assert _capture_status(30, 6) == "WATCH"
    def test_watch_boundary(self):  assert _capture_status(11, 6) == "WATCH"
    def test_prepare_upper(self):   assert _capture_status(10, 6) == "PREPARE"
    def test_prepare_lower(self):   assert _capture_status(2,  6) == "PREPARE"
    def test_entry_day_of(self):    assert _capture_status(0,  6) == "ENTRY"
    def test_entry_day_before(self):assert _capture_status(1,  6) == "ENTRY"
    def test_exit_d1(self):         assert _capture_status(-1, 6) == "EXIT"
    def test_exit_d6(self):         assert _capture_status(-6, 6) == "EXIT"
    def test_done_after_exit(self): assert _capture_status(-7, 6) == "DONE"


class TestCapturePlan:
    def test_all_statuses_have_plan(self):
        for status in ("WATCH", "PREPARE", "ENTRY", "EXIT", "DONE"):
            plan = _capture_plan(status)
            assert isinstance(plan, str) and len(plan) > 0


# ---------------------------------------------------------------------------
# get_capture_calendar / get_capture_table
# ---------------------------------------------------------------------------

class TestGetCaptureCalendar:
    _REF = date(2026, 3, 16)

    def test_returns_list(self, svc):
        records = svc.get_capture_calendar(today=self._REF)
        assert isinstance(records, list)

    def test_tier_filter_respected(self, svc):
        records = svc.get_capture_calendar(min_tier=1, today=self._REF)
        for r in records:
            assert r.tier == 1

    def test_window_respected_forward(self, svc):
        from datetime import timedelta
        records = svc.get_capture_calendar(days_ahead=14, post_ex_days=0, today=self._REF)
        cutoff = self._REF + timedelta(days=14)
        for r in records:
            assert r.ex_date <= cutoff

    def test_window_respected_backward(self, svc):
        from datetime import timedelta
        records = svc.get_capture_calendar(days_ahead=0, post_ex_days=6, today=self._REF)
        start = self._REF - timedelta(days=6)
        for r in records:
            assert r.ex_date >= start

    def test_sorted_by_days_to_ex(self, svc):
        records = svc.get_capture_calendar(today=self._REF)
        days = [r.days_to_ex for r in records]
        assert days == sorted(days)

    def test_capture_table_has_status_column(self, svc):
        df = svc.get_capture_table(today=self._REF)
        if not df.empty:
            assert "Статус" in df.columns
            assert "План" in df.columns

    def test_capture_table_status_values_valid(self, svc):
        df = svc.get_capture_table(today=self._REF)
        valid = {"WATCH", "PREPARE", "ENTRY", "EXIT", "DONE"}
        for v in df["Статус"]:
            assert v in valid

    def test_capture_table_empty_on_no_data(self, tmp_path):
        svc2 = DividendService(data_dir=tmp_path)
        assert svc2.get_capture_table().empty


# ---------------------------------------------------------------------------
# DividendService with missing files
# ---------------------------------------------------------------------------

class TestDividendServiceMissingFiles:
    def test_missing_dividends_returns_empty(self, tmp_path):
        svc = DividendService(data_dir=tmp_path)
        assert svc.get_calendar() == []

    def test_missing_declared_still_works(self, tmp_path):
        import json, shutil
        shutil.copy(_DATA_DIR / "dividends.json", tmp_path / "dividends.json")
        svc = DividendService(data_dir=tmp_path)
        records = svc.get_calendar(today=date(2026, 3, 16))
        assert isinstance(records, list)
        for r in records:
            assert r.confirmed is False
