"""Tests for MarketService — equity universe and sector loading."""

from pathlib import Path

from moex_dashboard.services.market_service import MarketService


# Use the real data/ directory for integration tests
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TestMarketServiceEquities:
    def setup_method(self):
        self.svc = MarketService(data_dir=_DATA_DIR)

    def test_equities_not_empty(self):
        equities = self.svc.get_equities()
        assert len(equities) > 100  # snapshot has 251 + consensus extras

    def test_equity_has_ticker(self):
        equities = self.svc.get_equities()
        for eq in equities:
            assert eq.ticker, "Every equity must have a ticker"

    def test_equity_with_consensus(self):
        """LENT is in both snapshot.json and consensus.json — should have fundamentals."""
        equities = self.svc.get_equities()
        lent = next((e for e in equities if e.ticker == "LENT"), None)
        assert lent is not None
        assert lent.target is not None  # from consensus
        assert lent.sales is not None

    def test_equity_with_price(self):
        """VTBR is in snapshot.json — should have price."""
        equities = self.svc.get_equities()
        vtbr = next((e for e in equities if e.ticker == "VTBR"), None)
        assert vtbr is not None
        assert vtbr.price is not None
        assert vtbr.price > 0


class TestMarketServiceSectors:
    def setup_method(self):
        self.svc = MarketService(data_dir=_DATA_DIR)

    def test_sectors_count(self):
        sectors = self.svc.get_sectors()
        assert len(sectors) == 8  # 8 MOEX sector indices

    def test_sector_has_signal(self):
        sectors = self.svc.get_sectors()
        for s in sectors:
            assert s.code, "Sector must have code"
            assert s.signal in ("LONG", "SHORT", "FLAT", ""), f"Bad signal: {s.signal}"

    def test_sector_has_momentum(self):
        sectors = self.svc.get_sectors()
        moexeu = next((s for s in sectors if s.code == "MOEXEU"), None)
        assert moexeu is not None
        assert moexeu.m3 is not None


class TestMarketServiceMissing:
    def test_missing_data_dir(self, tmp_path):
        """Service should return empty lists for missing files."""
        svc = MarketService(data_dir=tmp_path)
        assert svc.get_equities() == []
        assert svc.get_sectors() == []
