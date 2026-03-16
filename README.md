# MOEX Arbitrage Dashboard

A Python/Streamlit analytical terminal for the Moscow Exchange (MOEX) — arbitrage
opportunities, sector rotation signals, dividend capture, and perpetual futures funding.

Built as a reverse-engineering study of the [Packman Monitor](https://www.packmanmarkets.ru/)
dashboard, using the public [MOEX ISS API](https://iss.moex.com) (no auth required).

---

## Features

| Tab | Sub-tabs | Content |
|---|---|---|
| **Арбитраж** | Cash-and-Carry, Reverse C&C, Calendar FX, Cross-Instrument, Cross-FX, Cross-Gold, CIP Arb, Funding | 8 arbitrage strategies with live implied rates |
| **Relative Value** | Curve Shape, Calendar Commodity, Rate Spread | Contango/backwardation signals |
| **Кривые** | — | Term structure per asset (36+ instruments) |
| **Акции** | Carry кривые, Дивиденды | Stock carry + dividend calendar (DSI-tiered, 180-day) |
| **Стратегии** | Сектор Ротация, Momentum Portfolio, Захват дивидендов, Преф/Обычка | 4 strategy sub-tabs |

**Arbitrage strategies:**
- Cash-and-Carry: `Implied Rate = (F/S − 1) × 365/Days` vs КС ЦБ / RUSFAR
- Calendar FX: near/far forward rate spreads across Si, Eu, CR
- CIP Arb: `Implied USDCNY = Si / CR` vs spot USDCNY
- Cross-Gold: `GL_fair = GD × USDRUB / 31.1035` deviation
- Perpetual Funding: MOEX funding formula with minute candles

**Strategy signals:**
- Sector Rotation: 8 MOEX sector indices ranked by m3 momentum → LONG/SHORT/FLAT
- Momentum Portfolio: top-scored stocks within LONG sectors (upside + rec + div yield)
- Dividend Capture: ENTRY/PREPARE/EXIT/WATCH workflow, Tier 1/2 DSI classification
- Pref/Ordinary backtest: 12-year equity curves (SBER/P, TATN/P, RTKM/P, Portfolio)

---

## Architecture

```
Streamlit UI (ui/)
    ↓
services/              ← domain layer (stateless, orchestration only)
    ├── market_service.py              live snapshot + equity universe + sectors
    ├── arbitrage_service.py           7 arbitrage strategies → DataFrames
    ├── sector_momentum_service.py     m1/m3/m6/m12 ranking + LONG/SHORT/FLAT
    ├── funding_service.py             perpetual funding pipeline
    ├── momentum_portfolio_service.py  top-stock picker within LONG sectors
    └── dividend_service.py            dividend calendar, tiers, capture workflow
    ↓
data/  +  calc/        ← I/O and pure formulas (no business logic)
    ├── data/moex_api.py       MOEX ISS HTTP wrapper (retry, parse)
    ├── data/spot.py           currencies, indices, stocks
    ├── data/futures.py        FORTS futures (all expirations)
    ├── data/rates.py          RUSFAR, КС ЦБ
    ├── data/perpetual.py      perpetual specs + minute candles
    ├── calc/arbitrage.py      implied_rate, fair_value, basis, carry
    ├── calc/cip.py            CIP, si/eu parity, gold parity
    ├── calc/funding.py        D, funding formula, annualization
    └── calc/stocks.py         implied_dividend, dividend_yield
```

The UI layer calls only `services/*`. Services own orchestration and filtering;
`calc/*` contains pure functions with no I/O.

---

## Quickstart

```bash
# Install dependencies (requires Python 3.14+)
uv sync

# Run dashboard
uv run streamlit run src/moex_dashboard/app.py

# Run tests
uv run python -m pytest tests/ -q
```

---

## Data Sources

| Source | What | Auth |
|---|---|---|
| `iss.moex.com` | Live quotes, futures, RUSFAR, index history, sector prices | None |
| `data/snapshot.json` | Sector signals + equity universe (251 stocks, Feb 2026) | Static |
| `data/consensus.json` | Analyst consensus — target, rec, fundamentals (108 stocks) | Static |
| `data/dividends.json` | Upcoming dividends with DSI scores (304 records) | Static |
| `data/declared_divs.json` | Confirmed declared dividends with payment dates | Static |
| `data/backtest_data.json` | Pref/Ordinary backtest equity curves (627 weeks, 2013–2026) | Static |

Live data: ~15 min delay (MOEX ISS standard). Auto-refresh every 30 seconds.

---

## Key Formulas

| Formula | Expression |
|---|---|
| Implied Rate | `(F/S − 1) × 365/Days` |
| Fair Value | `S × (1 + КС × Days/365)` |
| CIP (Implied USDCNY) | `Si_futures / CR_futures` |
| Forward Premium | `(Impl/Spot − 1) × 365/Days` |
| Si Parity | `CNYRUB × USDCNY` |
| Eu Parity | `USDRUB × EURUSD` |
| Gold Parity | `GD_usd × USDRUB / 31.1035` |
| Perpetual Funding | `MIN(L2, MAX(−L2, MIN(−L1, D) + MAX(L1, D)))` |
| Sector Signal | Top-2 m3 → LONG, Bottom-2 m3 → SHORT |
| Stock Score | `upside% + rec_score(buy=30/hold=15/sell=0) + div_yield%` |
| DSI Tier 1 | DSI ≥ 0.5 (reliable dividend history) |
| DSI Tier 2 | DSI ≥ 0.25 (moderate dividend history) |

---

## Tests

132 unit tests, no network calls (synthetic fixtures + local JSON).

```bash
uv run python -m pytest tests/ -q
# 132 passed
```

| File | Tests | What's tested |
|---|---|---|
| `test_calc.py` | 27 | All pure calc formulas |
| `test_arbitrage_service.py` | 10 | 7 arbitrage strategies |
| `test_funding_service.py` | 6 | Perpetual funding pipeline |
| `test_market_service.py` | 8 | Equity universe + sector loading |
| `test_sector_momentum_service.py` | 17 | Momentum ranking, signal assignment |
| `test_momentum_portfolio_service.py` | 22 | Stock scoring, sector filtering |
| `test_dividend_service.py` | 42 | Calendar, tiers, capture workflow |

---

## Project Structure

```
src/moex_dashboard/
├── app.py                          Streamlit entry point (5 tabs, auto-refresh 30s)
├── config.py                       ASSET_MAP, tickers, constants
├── models.py                       SpotQuote, FuturesContract, MarketSnapshot (Pydantic)
├── data/                           MOEX ISS I/O layer
├── calc/                           Pure calculation functions (no I/O)
├── services/
│   ├── market_service.py           Snapshot + equity universe + sector map
│   ├── arbitrage_service.py        7 arbitrage methods → DataFrames
│   ├── sector_momentum_service.py  Sector ranking (snapshot or live MOEX ISS)
│   ├── funding_service.py          Perpetual USDRUBF/EURRUBF/CNYRUBF
│   ├── momentum_portfolio_service.py  Stock picker: LONG sectors → scored watchlist
│   └── dividend_service.py         Calendar (DSI tiers) + WATCH/PREPARE/ENTRY/EXIT
└── ui/
    ├── tab_arbitrage.py            8 sub-tabs
    ├── tab_relative.py             3 sub-tabs
    ├── tab_curves.py               Per-asset term structure
    ├── tab_stocks.py               Carry curves + dividend calendar (2 sub-tabs)
    ├── tab_strategies.py           Sector Rotation, Momentum Portfolio, Div Capture, Backtest
    └── _styling.py                 Color formatting helpers
data/                               Static JSON snapshots (Feb 2026)
tests/                              132 unit tests (7 test files)
```

---

## Roadmap

- [x] Phase 1–3: Data, Calc, UI layers
- [x] Phase 4: Service layer (Pydantic models, domain services)
- [x] Phase 5: Momentum Portfolio — top-sector stock picker
- [x] Phase 6: Dividend Service — calendar, DSI tiers, capture workflow
- [ ] FastAPI layer (`api/`) — decouple frontend from services
- [ ] Historical data store + backtest engine
- [ ] VPS deployment

---

*Data from [MOEX ISS API](https://iss.moex.com) — public, no authentication required.*
