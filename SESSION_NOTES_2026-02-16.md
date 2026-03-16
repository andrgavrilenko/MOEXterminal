# Session Notes - 2026-02-16

## What we did
- Reviewed docs: `MOEX_Dashboard_TZ.md`, `MOEX_Arbitrage_TZ_Full.txt`.
- Extracted core idea: MOEX arbitrage analytics app (educational, not trade execution).
- Produced a Codex/AI-CLI implementation model in sessions.
- Performed PM-style review and narrowed MVP scope.

## Agreed implementation model (AI-CLI)
1. Session 1: Skeleton + config + health + disclaimer.
2. Session 2: ISS ingestion + normalized market snapshot + retries/cache/stale flags.
3. Session 3: Core formulas + tests.
4. Session 4: Signal engine for 2 strategies first (`Cash&Carry`, `Calendar FX`).
5. Session 5: Minimal UI (`Opportunity Feed`, `Signal Detail`, CSV export, watchlist tags).
6. Session 6: Hardening + deploy + runbook.

## PM adjustments captured
- Keep MVP narrow: no full multi-tab clone.
- Define success metric: identify top opportunities fast.
- Add explicit acceptance criteria/gates per session.
- Keep no-execution boundary and educational disclaimer.

## First task for tomorrow
- Start Session 1: create project skeleton and interfaces (`MarketSnapshot`, `Signal`, config), plus health page.
