# MOEX Arbitrage Dashboard

A Python/Streamlit analytical terminal for the Moscow Exchange (MOEX) — arbitrage
opportunities, sector rotation signals, and perpetual futures funding analysis.

Built as a reverse-engineering study of the [Packman Monitor](https://www.packmanmarkets.ru/)
dashboard, using the public [MOEX ISS API](https://iss.moex.com) (no auth required).

---

## Features

| Tab | Content |
|---|---|
| **Arbitrage** | Cash-and-Carry, Reverse C&C, Calendar FX, Cross-FX, Cross-Gold, Cross-Instrument, CIP Arb, Perpetual Funding |
| **Relative Value** | Curve Shape, Calendar Commodity, Rate Spread |
| **Curves** | Term structure per asset (36+ instruments) |
| **Stocks** | Dividend carry, implied dividends |

**Arbitrage strategies covered:**
- Cash-and-Carry: `Implied Rate = (F/S − 1) × 365/Days` vs КС ЦБ / RUSFAR
- Calendar FX: near/far forward rate spreads across Si, Eu, CR
- CIP Arb: `Implied USDCNY = Si / CR` vs spot USDCNY
- Cross-Gold: `GL_fair = GD × USDRUB / 31.1035` deviation
- Perpetual Funding: MOEX funding formula with minute candles

---

## Architecture

```
Streamlit UI
    ↓
services/          ← domain layer (stateless, no side effects)
    ├── market_service.py           live snapshot + equities + sector map
    ├── arbitrage_service.py        7 arbitrage strategies → DataFrames
    ├── sector_momentum_service.py  m1/m3/m6/m12 ranking + LONG/SHORT/FLAT
    └── funding_service.py          perpetual funding pipeline
    ↓
data/  +  calc/    ← I/O and pure formulas
    ├── data/moex_api.py            MOEX ISS HTTP wrapper (retry, parse)
    ├── data/spot.py                currencies, indices, stocks
    ├── data/futures.py             FORTS futures (all expirations)
    ├── data/rates.py               RUSFAR, КС ЦБ
    ├── data/perpetual.py           perpetual specs + minute candles
    ├── calc/arbitrage.py           implied_rate, fair_value, basis, carry
    ├── calc/cip.py                 CIP, si/eu parity, gold parity
    ├── calc/funding.py             D, funding formula, annualization
    └── calc/stocks.py              implied_dividend, dividend_yield
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
uv run python -m pytest tests/ -v
```

---

## Data Sources

| Source | What | Auth |
|---|---|---|
| `iss.moex.com` | Live quotes, futures, RUSFAR, index history | None |
| `data/consensus.json` | Analyst consensus (108 stocks, Feb 2026) | Static snapshot |
| `data/snapshot.json` | Sector signals + equity universe (Feb 2026) | Static snapshot |
| `data/dividends.json` | Historical dividend base | Static snapshot |

Live data has a ~15 min delay (MOEX ISS standard). The dashboard auto-refreshes
every 30 seconds.

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

---

## Tests

62 unit tests, no network calls required (synthetic fixtures + local JSON).

```bash
uv run python -m pytest tests/ -q
# 62 passed
```

---

## Project Structure

```
src/moex_dashboard/
├── app.py                  Streamlit entry point
├── config.py               ASSET_MAP, tickers, constants
├── models.py               SpotQuote, FuturesContract, MarketSnapshot
├── data/                   MOEX ISS I/O layer
├── calc/                   Pure calculation functions
├── services/               Domain services (Phase 1–4 complete)
└── ui/                     Streamlit rendering only
data/                       Static JSON snapshots (Feb 2026)
tests/                      62 unit tests
```

---

## Roadmap

- [ ] Phase 5: `momentum_portfolio_service` — top-sector stock picker
- [ ] Phase 6: `dividend_service` — dividend capture calendar + arb
- [ ] FastAPI layer (`api/`) — decouple frontend from services
- [ ] Historical data store + backtest engine
- [ ] VPS deployment

---

*Data from [MOEX ISS API](https://iss.moex.com) — public, no authentication required.*
