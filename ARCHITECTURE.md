# MOEX Arbitrage Dashboard — Architecture Plan

## 1. Product Vision

Последовательность от данных к решениям:

1. **Картина рынка** — spot, futures, rates, sectors, базовый фундаментал
2. **Арбитраж** — FX calendar, convergence, funding, linked assets
3. **Sector momentum** — ranking секторов по momentum
4. **Momentum-портфель** — лидирующий сектор + лучшие акции внутри
5. **Dividend strategy** — event-driven на дивидендных отсечках

---

## 2. Layer Architecture

```
ui/                  Streamlit (сейчас напрямую в services, позже через API)
  |
api/                 FastAPI, Pydantic-контракты, /api/v1/
  |
services/            Доменная логика, оркестрация
  |
data/   +   calc/    I/O (MOEX ISS, files, DB) + чистые формулы
```

### Принципы

- **services/** — главный слой продукта. Каждый сервис собирает готовую доменную сущность.
- **data/** — только получение данных (MOEX, JSON, DB). Без бизнес-логики.
- **calc/** — чистые формулы. Без I/O, без side effects.
- **api/** — тонкий HTTP-слой: парсинг params, статус-коды, сериализация. Логика в services.
- **ui/** — только отображение. Streamlit вызывает services напрямую (MVP), позже через api_client.

### Transition strategy

```
MVP:   Streamlit -> services -> data + calc
Then:  Streamlit -> api_client -> FastAPI -> services -> data + calc
Later: React/Vue -> FastAPI -> services -> data + calc
```

api_client.py появляется при включении FastAPI, не раньше.

---

## 3. File Structure

```
src/moex_dashboard/
|
|-- models.py                      # Pydantic BaseModel (replace dataclass)
|-- config.py                      # Constants, ASSET_MAP, thresholds
|-- app.py                         # Streamlit entry point
|
|-- data/                          # I/O layer
|   |-- moex_api.py                # MOEX ISS wrapper (retry, parse)
|   |-- spot.py                    # Spot currencies, indices, stocks
|   |-- futures.py                 # FORTS futures loader
|   |-- rates.py                   # RUSFAR, key rate
|   |-- perpetual.py               # Perpetual FX futures
|   |-- snapshot.py                # MarketSnapshot builder (legacy, used until market_service ready)
|   |
|   +-- historical/                # NEW -- historical data for backtests
|       |-- __init__.py
|       |-- catalog.py             # Contract universe: all tickers + listing/expiry dates
|       |-- futures_hist.py        # Download + store futures history (all expirations)
|       |-- spot_hist.py           # Download + store spot history
|       |-- rates_hist.py          # Download + store RUSFAR/key_rate history
|       +-- store.py               # Parquet storage + manifest (versioned datasets)
|
|-- calc/                          # Pure formulas (no I/O)
|   |-- arbitrage.py               # implied_rate, fair_value, basis, carry_premium
|   |-- cip.py                     # CIP, parity, gold deviation
|   |-- funding.py                 # D, funding, annualized
|   |-- stocks.py                  # implied_dividend, dividend_yield
|   +-- pipeline.py                # TRANSITIONAL: absorbed into services, then deleted
|
|-- services/                      # NEW -- domain logic
|   |-- market_service.py          # Phase 1
|   |-- funding_service.py         # Phase 2
|   |-- arbitrage_service.py       # Phase 3
|   |   |-- fx_calendar
|   |   |-- perp_convergence       # uses funding_service.get_rates()
|   |   +-- pair_convergence       # linked assets (SBER/SBERP, TATN/TATNP, RTKM/RTKMP)
|   |-- sector_momentum_service.py # Phase 4
|   |-- momentum_portfolio_service.py  # Phase 5 (post-MVP)
|   |-- dividend_service.py        # Phase 6 (post-MVP)
|   |
|   +-- backtest/                  # Post-MVP -- backtesting engine
|       |-- __init__.py
|       |-- engine.py              # Replay historical snapshots
|       |-- runner.py              # Async job runner (APScheduler/RQ)
|       |-- config.py              # Roll rules, calendar, execution rules, look-ahead protection
|       |-- metrics.py             # Sharpe, PnL, drawdown, win rate
|       |-- costs.py               # Commissions, margin (GO), slippage
|       +-- strategies/
|           |-- cash_and_carry.py
|           |-- calendar_spread.py
|           |-- cross_fx.py
|           |-- cip.py
|           +-- pair_convergence.py
|
|-- api/                           # NEW -- HTTP layer
|   |-- main.py                    # FastAPI app + middleware (request_id, structlog)
|   |-- deps.py                    # TTLCache + lock (single worker MVP), DI
|   |-- errors.py                  # ErrorResponse model
|   |-- schemas/
|   |   |-- common.py              # BaseResponse, SourceStatus, PaginationParams
|   |   |-- market.py
|   |   |-- funding.py
|   |   |-- arbitrage.py
|   |   +-- portfolio.py
|   +-- routes/
|       |-- health.py
|       |-- market.py
|       |-- funding.py
|       |-- arbitrage.py
|       |-- strategies.py
|       |-- portfolio.py
|       +-- dividends.py
|
+-- ui/                            # Streamlit -- thin client
    |-- api_client.py              # Appears when FastAPI enabled; fallback -> services + banner
    |-- sidebar.py
    |-- tab_arbitrage.py
    |-- tab_relative.py
    |-- tab_curves.py
    |-- tab_stocks.py
    |-- _arb_extras.py
    +-- _styling.py
```

---

## 4. Services & Dependencies

```
market_service
  +-- spot, futures, rates, consensus.json, sector_map

funding_service                          (standalone, heavy, separate TTL)
  +-- data/perpetual.py

arbitrage_service
  |-- depends: market_service
  |-- depends: funding_service (scalar results only: annualized rates)
  +-- subdomains: fx_calendar, perp_convergence, pair_convergence

sector_momentum_service
  +-- depends: market_service (sector_map + index history)

momentum_portfolio_service
  |-- depends: market_service
  +-- depends: sector_momentum_service

dividend_service
  |-- depends: market_service
  +-- depends: dividends.json, declared_divs.json
```

---

## 5. API Endpoints

### Responses

Every response includes:
```json
{
  "request_id": "uuid",
  "as_of": "2026-03-16T10:30:00",
  "source_status": {
    "moex_iss": {"status": "ok", "age_sec": 12, "last_ok_at": "2026-03-16T10:29:48"},
    "local_json": {"status": "ok", "age_sec": 86400, "last_ok_at": "2026-03-15T10:30:00"}
  },
  "data": { ... }
}
```

`as_of` in MVP = timestamp of last fetch (informational).
`?as_of=` query param = real historical lookup (post-MVP, requires snapshot store).

### Error model

```json
{
  "error_code": "MOEX_TIMEOUT",
  "message": "MOEX ISS did not respond within 10s",
  "http_status": 504,
  "retryable": true,
  "upstream": "moex_iss",
  "timestamp": "2026-03-16T10:30:05",
  "request_id": "uuid",
  "details": null
}
```

### Pagination

Default: `?limit=100&offset=0&sort_by=ticker&sort_order=asc`
Heavy endpoints: `/market/equities`, `/market/futures`
Optional filters: `?sector=MOEXFN&fields=ticker,price,pe&updated_since=...`

### Endpoint list

```
GET /api/v1/health

# Market (Phase 1)
GET /api/v1/market/snapshot
GET /api/v1/market/equities      ?limit, offset, sector, fields
GET /api/v1/market/sectors
GET /api/v1/market/futures        ?limit, offset, asset, fields

# Funding (Phase 2)
GET /api/v1/funding/table
GET /api/v1/funding/{ticker}
GET /api/v1/funding/signals

# Arbitrage (Phase 3) -- NO /arbitrage/funding, use /funding/* directly
GET /api/v1/arbitrage/fx-calendar
GET /api/v1/arbitrage/perp-convergence
GET /api/v1/arbitrage/linked-assets

# Strategies (Phase 4)
GET /api/v1/strategies/sectors
GET /api/v1/strategies/sectors/leaderboard

# Portfolio (Phase 5, post-MVP)
GET /api/v1/portfolio/momentum
GET /api/v1/portfolio/momentum/candidates
GET /api/v1/portfolio/momentum/sector/{sector}

# Dividends (Phase 6, post-MVP)
GET /api/v1/dividends/calendar
GET /api/v1/dividends/capture
GET /api/v1/dividends/arbitrage

# Backtests (post-MVP, async)
POST /api/v1/backtest/run         -> returns {run_id}
GET  /api/v1/backtest/{run_id}    -> status, progress, result
```

### TTL cache

| Endpoint group     | TTL   | Rationale                        |
|--------------------|-------|----------------------------------|
| /market/snapshot   | 30s   | Core data, frequent refresh      |
| /market/equities   | 60s   | Less volatile                    |
| /market/sectors    | 60s   |                                  |
| /funding/table     | 60s   | Candle-based, moderate freshness |
| /funding/{ticker}  | 120s  | Heavy (minute candles)           |
| /strategies/*      | 300s  | History-based calculations       |
| /portfolio/*       | 300s  |                                  |
| /dividends/*       | 600s  | Event-driven, slow-changing      |

MVP: TTLCache in-process + single uvicorn worker (explicit constraint).
Scale: Redis when workers > 1.

---

## 6. Phases

```
Phase 1: market_service    -> /market/*
Phase 2: funding_service   -> /funding/*
Phase 3: arbitrage_service -> /arbitrage/*
Phase 4: sector_momentum   -> /strategies/sectors
--- MVP boundary ---
Phase 5: momentum_portfolio -> /portfolio/momentum
Phase 6: dividend_service   -> /dividends/*
Phase 7: backtest engine    -> /backtest/*
```

Each phase: service -> Pydantic schemas -> route -> Streamlit tab.

### pipeline.py migration

- Phase 1: services/ import functions from pipeline.py
- Phase 2+: each service absorbs its pipeline functions
- When pipeline.py is empty: delete it

### models.py migration

Direct replacement: `@dataclass` -> `BaseModel` (4 small classes, 44 lines).
No adapter layer needed.

---

## 7. Backtest Architecture (post-MVP)

### Historical data challenges

**Volume estimate:** 100s-1000s of MOEX ISS requests per asset class, not ~50.
Each expired contract = separate request + pagination.

**Contract catalog first:**
```
data/historical/catalog.py:
  1. Fetch all contracts ever listed for asset_code (MOEX ISS /history/ endpoint)
  2. Store: secid, asset_code, listing_date, expiry_date, last_trade_date
  3. This is the universe; history download iterates over it
```

**Data gaps:**
- key_rate: not daily in MOEX ISS, need CBR source + ffill policy
- RUSFAR: may have missing dates -> ffill + gap counter
- Corporate events (dividends, splits) for pref/common and sector strategies -> need adjustment layer

**Look-ahead bias protection:**
```python
# backtest/config.py
EXECUTION_DELAY = 1  # signal on day T, execute on T+1
PRICE_FIELD = "close"  # or "open" of T+1
LOOK_AHEAD_CHECK = True  # engine validates no future data leaks
```

**Async execution:**
Backtests are heavy (minutes to hours). Must be async jobs:
```
POST /api/v1/backtest/run
  -> creates job, returns {run_id, status: "queued"}

GET /api/v1/backtest/{run_id}
  -> {status: "running", progress: 45, eta_sec: 120}
  -> {status: "done", result: {sharpe: 1.8, pnl: [...], ...}}
```

Runner: APScheduler (MVP) or RQ/Celery (scale).

### Storage

MVP: Parquet files + manifest.json (dataset versioning).
Scale: DuckDB or Postgres for metadata + Parquet for timeseries.

```
data/historical/
  datasets/
    futures_Si_2020_2026.parquet
    spot_USDRUB_2020_2026.parquet
    rates_RUSFAR_2020_2026.parquet
  manifest.json   # {dataset_id, created_at, rows, date_range, checksum}
```

---

## 8. Operational Decisions

### Feature flags

```python
# config.py
FEATURE_API_ENABLED = False      # Streamlit -> services directly (MVP)
FEATURE_FALLBACK_ENABLED = True  # API down -> direct services + UI warning
```

When API enabled, api_client.py:
```python
try:
    return api.get("/market/snapshot")
except ApiError:
    if config.FEATURE_FALLBACK_ENABLED:
        st.warning("API unavailable, direct MOEX access")
        return market_service.get_snapshot()
    raise
```

### Monitoring (lightweight)

- `structlog` with `request_id` propagated through api -> services -> data
- Two alert thresholds in config: `MAX_LATENCY_WARN=5s`, `MAX_STALE_AGE=60s`
- Log: fetch_duration, source_errors, cache_hits

### Local JSON refresh

Source: Packman API (unstable).
Policy: daily cron, retry 3x with backoff, checksum validation, keep last-good copy.
Degradation: if fetch fails, serve stale data + `source_status.local_json.status = "stale"`.

### API versioning

- v1 is the only version until external consumers exist
- Breaking change = v2 (new prefix, old stays)
- Field stability: required fields are immutable in v1, new fields always optional

---

## 9. Screens (target)

| Screen              | Service                    | Sub-screens                              |
|---------------------|----------------------------|------------------------------------------|
| Market              | market_service             | snapshot, equities, sectors, futures     |
| Arbitrage           | arbitrage + funding        | fx calendar, perp conv, funding, linked  |
| Sector Momentum     | sector_momentum_service    | ranking, signals                         |
| Momentum Portfolio  | momentum_portfolio_service | sector pick, stock picks, candidates     |
| Dividends           | dividend_service           | calendar, capture, arbitrage             |

---

## 10. What We Explicitly Defer

| Item                        | When                          | Why not now                         |
|-----------------------------|-------------------------------|-------------------------------------|
| Redis cache                 | workers > 1                   | Single worker sufficient for MVP    |
| Contract test framework     | External API consumers        | Internal consumer = our tests       |
| Formal SLA / error budget   | Production with real users    | Two config numbers suffice          |
| Cursor-based pagination     | Datasets > 10K rows           | 250 equities, 135 futures           |
| DuckDB/Postgres             | Backtest phase                | Parquet + manifest for MVP          |
| ?as_of= query param         | Snapshot store exists          | Informational as_of first           |
