# Codex_MOEX_Portal_Compact_Mapping.md

## 1) Screen -> Source -> Function -> Formula -> Output

| Screen | Data Source | Function / Module | Core Formula(s) | Key Output Columns |
|---|---|---|---|---|
| Арбитраж / Cash-and-Carry | Spot (CETS/indices), FORTS futures, KeyRate, RUSFAR | `calc.pipeline.build_arbitrage_table` | `implied=(F/S-1)*365/D`, `basis=F-S`, `premium=implied-rate_ref` | Актив, Контракт, Дней, Спот, Фьюч, Базис, Implied Rate, Премия к КС, Премия к RUSFAR |
| Арбитраж / Reverse C&C | Те же + дивидендные акции | `ui.tab_arbitrage._render_reverse_cc` + pipeline | Фильтр `implied < key_rate`; dividend play через implied div | Instrument, Детали, Profit, Действие |
| Арбитраж / Calendar FX | Валютные фьючерсы одного актива (near/far) | `ui.tab_arbitrage._render_calendar_fx` | `fwd=(F_far/F_near-1)*365/delta_days`, `delta_rate=rate_far-rate_near` | Актив, Ближний, Дальний, Δдней, Fwd Rate, Rate Diff |
| Арбитраж / Cross-Instrument | Пары MIX/MXI, RTS/RTSM | `calc.pipeline.build_cross_instrument_table` | `spread=price_a/price_b-1`, дифф implied rate | Инструмент, Детали, Profit, Действие |
| Арбитраж / Cross-FX | USDRUB, CNYRUB, EURRUB spot + Si/CR/Eu futures | `calc.cip.si_parity`, `calc.cip.eu_parity` + UI | `USDRUB_fair=CNYRUB*USDCNY`, `EURRUB_fair=USDRUB*EURUSD` | Экспирация, CR Rate, Si Rate, Eu Rate, Max Δ, Арб.пары |
| Арбитраж / Cross-Gold | GD, GL futures + USDRUB spot | `calc.pipeline.build_cross_gold_table`, `calc.cip.gold_parity` | `GL_fair=GD*USDRUB/31.1035`, `deviation=GL_mkt/GL_fair-1` | GL, GD, Impl.USDRUB, Mkt.USDRUB, Расхождение, Действие |
| Арбитраж / CIP Arb | Si/CR matched by expiry + Spot USDCNY | `calc.pipeline.build_cip_table`, `calc.cip.*` | `impl_usdcny=Si/CR`, `fwd_prem=(Impl/Spot-1)*365/D` | Экспирация, Дней, Si, CR, Impl.USDCNY, Spot USDCNY, Fwd Premium |
| Арбитраж / Funding | Perpetual prices/specs + minute candles + cash rate | `calc.funding.build_funding_table` | `Funding=min(L2,max(-L2,min(-L1,D)+max(L1,D)))`, `annual=Funding/Spot*365` | Funding, Predicted, Annualized, vs Cash, Suggested Action |
| Relative Value / Calendar Commodity | Commodity curves (BR, NG, metals) | RV pipeline/UI | near/far implied spread, seasonal carry | Актив, Ближний, Дальний, ΔRate, Абс.спред, Направление |
| Relative Value / Curve Shape | Full futures curve per asset | RV pipeline/UI | curve classification contango/backwardation/mixed | Актив, Контр., Front, Back, Форма, Спред |
| Relative Value / Rate Spread | Все инструменты с ранжированием carry | RV pipeline/UI | ranking by carry premium and rate differential | Тип, Стратегия, Инструмент, Детали, Profit, Действие |
| Div Arb & Carry | TQBR stocks + stock futures + KeyRate | `calc.pipeline.build_stocks_table`, `calc.stocks.*` | `fair=S*(1+r*D/365)`, `div_impl=fair-F`, `div%=div_impl/S` | Спот, Ближний/Дальний фьюч, rate, prog_div, div_yield, action |
| Market Data / Акции | Stock market quotes + stats | market data module | агрегаты/фильтры, мультипликаторы | Тикер, Сектор, Цена, Изм%, Прогн.див, Доход, Оборот, Сделки |
| Market Data / Корп.бонды | Bond quotes + duration/yield | market data module | YTM, duration, spread analytics | Выпуск, Рейтинг, Цена%, YTM, Duration, Купон, Погашение |
| Market Data / ОФЗ | OFZ list + yield metrics | market data module | YTM/Duration summary | Выпуск, Цена%, Доходн%, Дюрация, Купон, Погашение |
| Market Data / Фьючерсы | FORTS board stats | market data module | OI/volume/disbalance metrics | Тикер, OI, Объем, Buy/Sell, Disb, Спред |
| Консенсус Акции | Prices + target/reco/fundamentals | consensus module | `upside=(target/price-1)` | Тикер, Цена, Target, Upside, Рек, P/E, EV/EBITDA, DivYield |
| Стратегии / Преф-Обычка | Pref/common pair history | strategy module | z-score mean reversion | Пара, Ratio, Mean, Δabs, z-score, Signal |
| Стратегии / Сектор Ротация | Sector index momentum | strategy module | 1/3/6/12M momentum ranking | Сектор, perf windows, Signal (LONG/SHORT/FLAT) |
| Стратегии / Momentum | Multi-asset momentum board | strategy module | top/bottom momentum + acceleration | Asset, 1/3/6/12M, reason, Signal |
| Стратегии / Дивиденды | Dividend calendar/statistics | strategy module | historical edge around ex-div | Tier, Z, Avg%, WinRate, Months, Status |
| Макро | Macro time-series | macro module | selected indicator time-series | Series graph, period filters |
| Объёмы | Turnover/volume anomalies | volume module | `RVOL=Vol_today/Vol_avg_60d` | Name, Ticker, Vol, Turnover, x1d/x5d/x10d |
| OI Физ/Юр | MOEX participant positions | OI module | net/long/short by participant type | Физ long/short/net, Юр long/short/net, доли |
| Кривые | Term structure view | curves module | curve snapshot by class/asset/time-shift | Class, Asset, curve controls |

## 2) API Mapping (операционные)

| Domain | Endpoint | Purpose | Fields |
|---|---|---|---|
| Spot FX | `/engines/currency/markets/selt/boards/CETS/securities.json` | USDRUB/CNYRUB/EURRUB spot | `SECID,LAST` |
| Indices | `/engines/stock/markets/index/securities.json` | IMOEX/RTSI spot index | `SECID,CURRENTVALUE` |
| RUSFAR | `/engines/stock/markets/index/securities/RUSFAR.json` | Денежная ставка RUSFAR | `CURRENTVALUE` |
| Stocks | `/engines/stock/markets/shares/boards/TQBR/securities.json` | Spot по акциям | `SECID,LAST` |
| FORTS futures | `/engines/futures/markets/forts/securities.json` | Контракты, экспирации, цены | `SECID,ASSETCODE,LASTDELDATE,LAST,SETTLEPRICE` |
| Streamlit health | `GET /_stcore/health` | runtime healthcheck | `ok` |
| Streamlit host-config | `GET /_stcore/host-config` | frontend/runtime config | `allowedOrigins,...` |
| Streamlit stream | `WS /_stcore/stream` | server->browser data channel | protobuf messages |

## 3) Formula Registry (коротко)

| Formula ID | Expression | Used in |
|---|---|---|
| F01 implied_rate | `(F/S-1)*365/D` | C&C, Reverse, Calendar, Curves, Div |
| F02 fair_value | `S*(1+r*D/365)` | Div, stock carry |
| F03 carry_premium | `implied-r_ref` | C&C, RV Rate Spread |
| F04 basis | `F-S` | Arbitrage tables |
| F05 implied_usdcny | `Si/CR` | CIP |
| F06 forward_premium | `(Impl/Spot-1)*365/D` | CIP |
| F07 si_parity | `CNYRUB*USDCNY` | Cross-FX |
| F08 eu_parity | `USDRUB*EURUSD` | Cross-FX |
| F09 gold_parity | `GD*USDRUB/31.1035` | Cross-Gold |
| F10 implied_dividend | `fair-F` | Div Arb |
| F11 dividend_yield | `div_impl/S` | Div Arb |
| F12 funding_clamp | `min(L2,max(-L2,min(-L1,D)+max(L1,D)))` | Funding |
| F13 funding_annual | `Funding/Spot*365` | Funding |
