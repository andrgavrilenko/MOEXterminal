# Codex_MOEX_Portal_HLD_LLD.md

## 1. Scope и цель

Документ фиксирует архитектуру портала `RUSSIAN MARKET PACKMAN MONITOR`, маппинг формул, маппинг API и структуру экранов на основании:
- локальной реализации `src/moex_dashboard/*`
- дампов `MOEX_Technical_Dump.txt`, `MOEX_DevTools_Dump.txt`, `MOEX_extension_Session_Log.txt`
- визуального анализа скриншотов `screenshots/*`

Цель: дать техническую основу для воспроизведения/развития портала без прямого доступа к удаленному серверу.

---

## 2. HLD (High-Level Design)

### 2.1 Архитектурный стиль

- Тип: монолитное аналитическое веб-приложение на `Python + Streamlit`.
- UI и backend исполняются в одном процессе Streamlit.
- Данные рынка подтягиваются сервером (Python requests) из внешних API.
- Клиент (браузер) получает уже рассчитанные таблицы/метрики по Streamlit WebSocket.

### 2.2 Логические слои

1. Presentation Layer
- Streamlit pages/tabs/subtabs
- Таблицы, метрики, графики, экспорт CSV
- Основная навигация: Арбитраж, Relative Value, Div Arb & Carry, Market Data, Консенсус, Стратегии, Макро, Объёмы, OI, Кривые

2. Application/Domain Layer
- Расчет implied rates, carry premium, CIP, parity, дивидендных и funding метрик
- Построение display-ready таблиц под конкретные экраны

3. Data Access Layer
- Обертка над MOEX ISS (`fetch_iss`) с retry/timeout/parsing
- Загрузка spot, futures, rates, perpetual candles/specs
- Сборка единого `MarketSnapshot`

4. External Integrations
- MOEX ISS REST API
- CBR (ключевая ставка; в локальной версии зафиксирована в config)
- Streamlit transport endpoints (`/_stcore/*`)
- (по дампам) внешний webhook Fivetran

### 2.3 Контейнерная/процессная модель

- Один процесс Streamlit на `:8501`.
- Browser <-> Streamlit runtime через `WS /_stcore/stream`.
- Server -> MOEX ISS через HTTPS REST.
- Cache TTL ~30 сек (для market snapshot), отдельный кеш для тяжелых funding-данных.

### 2.4 Ключевой поток данных (E2E)

1. Пользователь открывает вкладку.
2. Streamlit инициирует/переиспользует state + cache.
3. Сервер делает запросы к MOEX ISS.
4. Собирается `MarketSnapshot` (spot/futures/rates/time/stale).
5. Calculation/pipeline строят таблицы под экран.
6. UI рендерит таблицы/графики/сигналы.
7. Через 30с выполняется автообновление.

### 2.5 Нефункциональные требования

- Near real-time обновление (шаг 30 сек).
- Деградация при частичной недоступности источников (флаг stale, частичный рендер).
- Понятная explainability: детализация формул в колонках таблиц.
- Расширяемость: добавление новых инструментов через `ASSET_MAP`.

---

## 3. LLD (Low-Level Design)

### 3.1 Структура модулей (локальная реализация)

- `src/moex_dashboard/app.py`:
  - entrypoint
  - `st.set_page_config`, tabs
  - `_get_snapshot()` с `@st.cache_data(ttl=30)`
  - автообновление (`sleep + rerun`)

- `src/moex_dashboard/data/moex_api.py`:
  - `fetch_iss(endpoint, params)`
  - retry, timeout, parse ISS blocks -> DataFrame

- `src/moex_dashboard/data/spot.py`:
  - `load_spot_currencies()`
  - `load_indices()`
  - `load_stock_spots()`

- `src/moex_dashboard/data/futures.py`:
  - `load_all_futures()`
  - merge securities + marketdata
  - фильтрация по `ASSET_MAP`
  - нормализация цены через `price_divisor`

- `src/moex_dashboard/data/rates.py`:
  - `load_rusfar()`
  - `get_key_rate()`

- `src/moex_dashboard/data/snapshot.py`:
  - `build_snapshot()` агрегирует все источники в `MarketSnapshot`

- `src/moex_dashboard/calc/arbitrage.py`:
  - implied rate / fair value / basis / premium

- `src/moex_dashboard/calc/cip.py`:
  - implied USDCNY, forward premium, parity, gold deviation

- `src/moex_dashboard/calc/funding.py`:
  - D, funding clamp-функция, annualized, таблица funding

- `src/moex_dashboard/calc/pipeline.py`:
  - `build_arbitrage_table`
  - `build_cip_table`
  - `build_curves_table`
  - `build_stocks_table`
  - `build_cross_gold_table`
  - `build_cross_instrument_table`

- `src/moex_dashboard/ui/*`:
  - sidebar + вкладки + визуальное форматирование

### 3.2 Основные доменные сущности

- `SpotQuote`: secid, name, price
- `FuturesContract`: secid, asset_code, expiry_date, price, days_to_expiry
- `MarketSnapshot`: timestamp, spots, futures, rusfar, key_rate, stale

### 3.3 Конфигурация и справочники

- `src/moex_dashboard/config.py`:
  - `BASE_URL=https://iss.moex.com/iss`
  - `CACHE_TTL_SECONDS`, `REQUEST_TIMEOUT`, `MAX_RETRIES`
  - `KEY_RATE`
  - `ASSET_MAP` (asset -> spot mapping + price_divisor + market)
  - списки спотов/индексов/акций

### 3.4 Транспорт Streamlit (по дампам)

- `GET /_stcore/health`
- `GET /_stcore/host-config`
- `GET /_stcore/allowed-message-origins`
- `WS /_stcore/stream` (основной канал данных/событий)

Важно: MOEX API вызывается на серверной стороне, не в браузере.

---

## 4. Mapping: Формулы -> код -> экраны

### 4.1 Базовые формулы carry/arbitrage

1. Implied Rate
- Формула: `(F / S - 1) * 365 / D`
- Где: `F` фьючерс, `S` спот, `D` дни до экспирации
- Код: `calc/arbitrage.py::implied_rate`
- Экраны: Арбитраж (C&C, Reverse, Calendar), Relative Value, Кривые, Div Arb

2. Fair Value
- Формула: `S * (1 + r * D / 365)`
- Где: `r` cash rate (КС/RUSFAR)
- Код: `calc/arbitrage.py::fair_value`
- Экраны: Cross-Instrument/stock-div блоки, Div Arb & Carry

3. Carry Premium
- Формула: `implied_rate - funding_rate`
- Код: `calc/arbitrage.py` (premium helper), pipeline-таблицы
- Экраны: C&C, Reverse, Rate Spread

4. Basis
- Формула: `F - S`
- Код: `calc/arbitrage.py::basis`
- Экраны: Арбитраж, кривые

### 4.2 CIP / parity

5. Implied USDCNY (через Si/CR)
- Формула: `Impl_USDCNY = Si_price / CR_price`
- Код: `calc/cip.py::implied_usdcny`
- Экран: `CIP Arb`

6. Forward Premium
- Формула: `(Impl/Spot - 1) * 365 / D`
- Код: `calc/cip.py::forward_premium`
- Экран: `CIP Arb`

7. Si parity
- Формула: `USDRUB_fair = CNYRUB * USDCNY`
- Код: `calc/cip.py::si_parity`
- Экран: `Cross-FX`

8. Eu parity
- Формула: `EURRUB_fair = USDRUB * EURUSD`
- Код: `calc/cip.py::eu_parity`
- Экран: `Cross-FX`

9. Cross-Gold parity
- Формула: `GL_fair = GD_USD * USDRUB / 31.1035`
- Код: `calc/cip.py::gold_parity`, `gold_deviation`
- Экран: `Cross-Gold`

### 4.3 Dividend / stocks

10. Implied Dividend
- Базово: `Div_impl = FairValue - Futures` (для выбранного контракта)
- Код: `calc/stocks.py::implied_dividend`
- Экраны: `Div Arb & Carry`, stocks summary

11. Dividend Yield
- Формула: `Div% = Div_impl / Spot`
- Код: `calc/stocks.py::dividend_yield`
- Экраны: Div/stock таблицы

### 4.4 Funding (perpetual)

12. Predicted Funding (MOEX-style clamp)
- Формула: `Funding = min(L2, max(-L2, min(-L1, D) + max(L1, D)))`
- Код: `calc/funding.py::calc_funding`
- Экраны: `Funding` саб-вкладка арбитража

13. Funding annualized
- Формулы:
  - `Funding_daily = Funding / Spot`
  - `Funding_annualized = Funding_daily * 365`
- Код: `calc/funding.py`
- Экран: `Funding`

---

## 5. Mapping: Экраны -> таблицы -> API

### 5.1 Арбитраж

- Cash-and-Carry / Reverse / Calendar FX
  - Источники: спот валют/индексов + фьючерсы FORTS + ставки
  - Таблицы: implied rate, basis, премия к КС/RUSFAR, action

- Cross-Instrument
  - Источники: пары MIX/MXI, RTS/RTSM
  - Метрика: spread и дифференциал implied rate

- Cross-FX
  - Источники: USD/RUB, CNY/RUB, EUR/RUB spot + фьючерсы Si/CR/Eu
  - Метрики: parity deviations

- Cross-Gold
  - Источники: GD/GL + USDRUB
  - Метрики: fair GL, deviation, trade action

- CIP Arb
  - Источники: Si + CR matched by expiry, spot USDCNY
  - Метрики: implied USDCNY, fwd premium, signal

- Funding
  - Источники: perpetual prices/specs + minute candles + cash rates
  - Метрики: D, predicted/indicative funding, annualized vs cash

### 5.2 Relative Value

- Calendar Commodity
  - Парные экспирации commodity futures, `Δrate`

- Curve Shape
  - Классификация формы кривой (contango/backwardation/mixed)

- Rate Spread
  - Ranking по spread и carry premium

### 5.3 Div Arb & Carry

- Источники: акции TQBR + stock futures
- Метрики: front/back implied rate, implied dividend, div yield, action

### 5.4 Market Data

- Акции: таблица по бумагам + секторные фильтры + агрегаты
- Корп.бонды/ОФЗ: доходность/дюрация, scatter + таблицы
- Фьючерсы: OI/volume/disbalance/спред и пр.

### 5.5 Консенсус Акции

- Источники: market prices + target/оценки (агрегированные)
- Метрики: upside, recommendation, мультипликаторы (P/E, EV/EBITDA, etc.)

### 5.6 Стратегии

- Преф/Обычка: mean reversion (z-score, backtest)
- Сектор ротация: momentum L/S
- Momentum: cross-asset scoreboard
- Дивиденды: календарь и сигнал buy/sell

### 5.7 Макро / Объемы / OI / Кривые

- Макро: timeseries (ключевая ставка и др.)
- Объемы: аномалии объема vs avg 60d
- OI Физ/Юр: позиции физиков/юриков по инструментам
- Кривые: term structure (фильтр по классу/активу/горизонту)

---

## 6. API спецификация (используемые и подтвержденные)

### 6.1 MOEX ISS (основные)

- Spot currency:
  - `/engines/currency/markets/selt/boards/CETS/securities.json`
  - columns: `SECID,LAST`

- Indices:
  - `/engines/stock/markets/index/securities.json`
  - columns: `SECID,CURRENTVALUE`

- RUSFAR:
  - `/engines/stock/markets/index/securities/RUSFAR.json`

- Stocks TQBR:
  - `/engines/stock/markets/shares/boards/TQBR/securities.json`
  - columns: `SECID,LAST`

- Futures FORTS:
  - `/engines/futures/markets/forts/securities.json`
  - blocks: `securities`, `marketdata`
  - columns: `SECID,SHORTNAME,LASTDELDATE,ASSETCODE` + `SECID,LAST,SETTLEPRICE`

### 6.2 Streamlit runtime endpoints

- `GET /_stcore/health`
- `GET /_stcore/host-config`
- `GET /_stcore/allowed-message-origins`
- `WS /_stcore/stream`

### 6.3 Дополнительные источники (по дампам)

- CBR XML daily (исторически упоминался в дампах)
- Fivetran webhook (интеграционный POST в оригинальном портале)

---

## 7. Правила данных и вычислений

- Нормализация цен фьючерсов строго через `ASSET_MAP.price_divisor`.
- Для commodities без спота база может быть front contract.
- Матчинг кросс-таблиц по экспирации (`expiry_date`).
- Если данных нет/неконсистентны: возврат пустой таблицы вместо падения.
- Snapshot может быть partial, UI должен уметь работать в degraded режиме (`stale`).

---

## 8. Риски и техдолг

- `KEY_RATE` в локальной реализации захардкожен; нужен автоматизированный источник/процедура обновления.
- Для некоторых экранов оригинального портала (консенсус/стратегии/макро) источник в проекте может быть частично реконструирован.
- Визуальные сигналы/цветовые правила завязаны на пороги; требуется единый конфиг порогов для повторяемости.
- Портал содержит много доменных таблиц; полезно выделить contracts/data-schema слой для строгой валидации.

---

## 9. Рекомендации к реализации v2

1. Вынести все формулы в отдельный `formula_registry` (id, input schema, output schema, unit, explanation).
2. Ввести `data contracts` для всех табличных моделей экрана.
3. Добавить source lineage в каждой таблице (какой endpoint, timestamp, quality flag).
4. Добавить тесты на финансовые инварианты (например, CIP/паритетные identity).
5. Добавить `observability`: latency fetch, %empty rows, stale-rate, errors per source.

---

## 10. Быстрый индекс для команды

- HLD: раздел 2
- LLD: раздел 3
- Формулы: раздел 4
- API: раздел 6
- Экранный маппинг: раздел 5
