# Codex Portal Config And Architecture

## 1. Goal

This document defines:
- which Packman-style sections should be built first
- the recommended product configuration for each phase
- the target architecture for the local Streamlit implementation

The goal is to avoid rebuilding the entire original portal at once and instead
ship the highest-value sections in a clean order.

---

## 2. Product Priorities

### P0. Core moat

Build first:
- Arbitrage
- Relative Value
- Futures Market Data
- Futures Curves
- OI Phys/Legal

Why first:
- this is the most differentiated part of the original product
- these sections directly support execution of arbitrage ideas
- they reuse the same market data backbone: spot, futures, curves, OI, rates

Business value:
- strongest unique value proposition
- closest to "Bloomberg for MOEX arbitrage"
- useful to active futures traders immediately

Implementation status today:
- Arbitrage: partly implemented
- Relative Value: partly implemented
- Futures Curves: partly implemented
- Futures Market Data: not implemented in local app
- OI Phys/Legal: not implemented in local app

### P1. Equities decision layer

Build second:
- Stocks Market Data
- Dividend Arbitrage
- Consensus
- Volume anomalies

Why second:
- these sections broaden the audience beyond pure derivatives traders
- they are easier to understand for users
- they complement arbitrage signals with stock-level context

Business value:
- increases daily utility
- makes the portal useful for both traders and investors

### P2. Bonds and macro context

Build third:
- OFZ
- Corporate Bonds
- Macro
- Calendar

Why third:
- important for context and fixed-income workflows
- useful, but not the main differentiator of the portal
- requires extra datasets and visualizations

### P3. Strategy and research layer

Build fourth:
- Preferred/Common
- Sector Rotation
- Momentum
- Dividend Capture
- Fundamentals

Why fourth:
- these are valuable, but mostly research and idea-generation modules
- they depend on either static datasets, backtests, or external analytics
- they are not needed for the first operational version

### P4. Long-tail expansion

Build last:
- Funds
- News
- Watchlist
- Heatmaps
- advanced personalization

Why last:
- high UX value, lower core trading value
- better added after the core workflows already work

---

## 3. Recommended Release Configuration

### Release 1

Sections:
- Arbitrage
- Relative Value
- Futures

Subsections:
- Cash-and-Carry
- Reverse C&C
- Calendar FX
- Cross-Instrument
- Cross-FX
- Cross-Gold
- CIP Arb
- Funding
- Curve Shape
- Calendar Commodity
- Rate Spread
- Futures Market Data
- Futures Curves
- OI Phys/Legal

Positioning:
- terminal for MOEX futures and arbitrage traders

### Release 2

Sections:
- Stocks
- Bonds

Subsections:
- Stocks Market Data
- Dividend Arbitrage
- Consensus
- Volume
- OFZ
- Corporate Bonds

Positioning:
- trading + investment workstation

### Release 3

Sections:
- Strategies
- Macro
- Calendar

Subsections:
- Preferred/Common
- Sector Rotation
- Momentum
- Dividend Capture
- Macro
- Calendar

Positioning:
- full research and execution platform

### Release 4

Sections:
- Fundamentals
- Funds
- News

Positioning:
- complete Packman-style portal

---

## 4. Recommended Information Architecture

Top-level navigation should be reduced to clear business domains:

1. Futures
- Market Data
- Curves
- OI Phys/Legal

2. Arbitrage
- Cash-and-Carry
- Reverse C&C
- Calendar FX
- Cross-Instrument
- Cross-FX
- Cross-Gold
- CIP Arb
- Funding

3. Relative Value
- Curve Shape
- Calendar Commodity
- Rate Spread

4. Stocks
- Market Data
- Dividend Arbitrage
- Consensus
- Volume
- Fundamentals

5. Bonds
- OFZ
- Corporate Bonds

6. Strategies
- Preferred/Common
- Sector Rotation
- Momentum
- Dividend Capture

7. Macro

8. Calendar

9. Funds

10. News

This structure is better than mirroring every historical Packman screen because
it groups features by user job-to-be-done rather than by implementation history.

---

## 5. Configuration Strategy

The portal should be config-driven.

Recommended config layers:

1. Product config
- which top-level sections are enabled
- which subsections are enabled
- labels, icons, sort order

2. Data-source config
- source type: live MOEX / local JSON / hybrid
- refresh interval
- failure behavior

3. Feature config
- CSV export enabled/disabled
- charts enabled/disabled
- auto-refresh enabled/disabled
- show-beta badge

4. Audience config
- trader mode
- investor mode
- simple mode
- pro mode

### Suggested config shape

```python
PORTAL_CONFIG = {
    "sections": [
        {
            "id": "futures",
            "label": "Futures",
            "enabled": True,
            "priority": 10,
            "children": [
                {"id": "futures_market_data", "enabled": True, "source": "live"},
                {"id": "futures_curves", "enabled": True, "source": "live"},
                {"id": "futoi", "enabled": True, "source": "json_or_api"},
            ],
        },
        {
            "id": "arbitrage",
            "label": "Arbitrage",
            "enabled": True,
            "priority": 20,
            "children": [
                {"id": "cash_and_carry", "enabled": True, "source": "live"},
                {"id": "reverse_cc", "enabled": True, "source": "live"},
                {"id": "calendar_fx", "enabled": True, "source": "live"},
                {"id": "cross_instrument", "enabled": True, "source": "live"},
                {"id": "cross_fx", "enabled": True, "source": "live"},
                {"id": "cross_gold", "enabled": True, "source": "live"},
                {"id": "cip", "enabled": True, "source": "live"},
                {"id": "funding", "enabled": True, "source": "live"},
            ],
        },
    ]
}
```

---

## 6. Target Technical Architecture

### 6.1 Layers

1. App shell
- page layout
- top navigation
- mode switch
- refresh controls

2. Section registry
- declarative section definitions
- maps section id -> renderer
- maps section id -> data dependencies

3. Data services
- market snapshot service
- OI service
- bonds service
- consensus service
- calendar service
- fundamentals service

4. Calculation layer
- pricing formulas
- parity formulas
- carry/funding formulas
- ranking logic

5. Presentation layer
- reusable table renderer
- reusable chart renderer
- reusable metric cards

### 6.2 Data architecture

Use three source modes:

1. Live
- direct MOEX ISS and related APIs
- used for core market tabs

2. Static snapshot
- local JSON datasets copied from original portal
- used for sections not yet rebuilt from raw sources

3. Hybrid
- live market prices + local static research data
- useful for consensus, strategies, dividends, funds

### 6.3 Module split

Recommended package growth:

- `src/moex_dashboard/app_shell/`
- `src/moex_dashboard/registry/`
- `src/moex_dashboard/services/`
- `src/moex_dashboard/data/`
- `src/moex_dashboard/calc/`
- `src/moex_dashboard/ui/`
- `src/moex_dashboard/features/`

Feature-oriented folders inside `features/`:

- `features/arbitrage/`
- `features/relative_value/`
- `features/futures/`
- `features/stocks/`
- `features/bonds/`
- `features/strategies/`
- `features/macro/`
- `features/calendar/`
- `features/funds/`
- `features/news/`

This is better than keeping all tabs flat under `ui/` once the portal grows.

---

## 7. Delivery Recommendation

### Phase A. Clean core

Do now:
- keep current arbitrage code as the seed
- add section registry
- split top-level navigation into Futures / Arbitrage / Relative Value / Stocks / Bonds
- add config-driven enable flags

### Phase B. Execution context

Add next:
- Futures Market Data
- OI Phys/Legal
- richer Curves

This makes arbitrage sections actually tradable, not just analytical.

### Phase C. Broaden user value

Add next:
- Stocks Market Data
- Dividend Arbitrage
- Consensus
- OFZ
- Corporate Bonds

### Phase D. Research stack

Add last:
- Strategies
- Macro
- Calendar
- Funds
- Fundamentals
- News

---

## 8. Final Recommendation

If the objective is to build a strong first product, do not start with the full
Packman clone.

Start with this configuration:
- Futures
- Arbitrage
- Relative Value
- Stocks (Dividend + Consensus only)

And this architecture:
- config-driven navigation
- feature registry
- shared data services
- feature-oriented modules
- hybrid live + static data model

This gives the shortest path to a usable product and keeps the project from
turning into a large undocumented Streamlit monolith.
