# MOEX Arbitrage Dashboard

Учебный проект: воспроизведение дашборда арбитражных возможностей на Московской бирже.

## Цель

Разобрать работающий прототип (RUSSIAN MARKET PACKMAN MONITOR на https://www.packmanmarkets.ru/), понять формулы и архитектуру, затем создать собственную реализацию.

## Задание

1. Проанализировать существующий дашборд (10 табов, 18 суб-табов)
2. Составить подробное ТЗ с формулами, API-эндпоинтами, архитектурой
3. Реализовать аналогичный инструмент на Python + Streamlit + MOEX ISS API

## Прогресс

### Этап 1: Анализ и ТЗ — ГОТОВО

- [x] Анализ дашборда по скриншотам (5 скриншотов всех табов)
- [x] Исследование MOEX ISS API (эндпоинты, формат данных)
- [x] Исследование формул арбитража (BCS, MOEX документация, CIP теория)
- [x] Создание ТЗ из технического анализа (Claude Code)
- [x] Анализ Extension_extract.txt (финансовый анализ от Claude Code Extension)
- [x] Объединение двух документов в единое ТЗ

**Результат:** `MOEX_Dashboard_TZ.md` — 1532 строки, полное ТЗ включающее:
- Архитектуру (Streamlit + pandas + MOEX ISS API)
- 8 формул с пошаговыми расчётами (Implied Rate, Fair Value, Basis, Daily Carry, CIP, Forward Premium, Si/Eu Parity)
- Все API-эндпоинты MOEX ISS
- Маппинг тикеров фьючерсов
- Структуру UI (4 таба, сайдбар, таблицы)
- Python-псевдокод ключевых функций
- План реализации (4 стадии)
- Глоссарий терминов

### Этап 2: Реализация — ЗАВЕРШЁН (Фазы 1–6)

- [x] Стадия 1: Data Layer — подключение к MOEX ISS API, парсинг, кеширование
- [x] Стадия 2: Calculation Layer — все формулы арбитража
- [x] Стадия 3: UI Layer — Streamlit интерфейс, таблицы, графики
- [x] Стадия 4: Service Layer — Pydantic модели, 6 доменных сервисов (Фазы 1–6)
- [ ] Стадия 5: Деплой на VPS

**Реализовано (актуально на март 2026):**
- **5 основных табов:** Арбитраж, Relative Value, Кривые, Акции, Стратегии
- **Арбитраж (8 суб-табов):** Cash-and-Carry, Reverse C&C, Calendar FX, Cross-Instrument, Cross-FX, Cross-Gold, CIP Arb, Funding
- **Relative Value (3 суб-таба):** Curve Shape, Calendar Commodity, Rate Spread
- **Акции (2 суб-таба):** Carry кривые + Дивиденды (304 события, DSI Tier 1/2, 180 дней)
- **Стратегии (4 суб-таба):**
  - Сектор Ротация: 8 MOEX-секторов, m1/m3/m6/m12 моментум, LONG/SHORT/FLAT
  - Momentum Portfolio: топ акции в LONG-секторах (апсайд + рек + дивиденд), 74 тикера
  - Захват дивидендов: WATCH/PREPARE/ENTRY/EXIT статусы, Tier 1/2, окно выхода D+N
  - Преф/Обычка: equity curves + недельная альфа (SBER/P, TATN/P, RTKM/P, Portfolio)
- Цветовая раскраска: зелёный/красный для ставок, статусов, рекомендаций
- Авто-обновление (30 сек) + CSV экспорт на всех таблицах
- **132 теста** — все проходят (7 файлов, без сетевых вызовов)

**Не реализовано:**
- Деплой на VPS
- FastAPI слой (api/) — разделение frontend/backend
- Исторические данные + бэктест-движок
- Консенсус-таб, Макро, Объёмы, OI Физ/Юр из оригинала
- Корпоративные облигации (corp_bonds.json готов, UI нет)

## Запуск

```bash
uv run streamlit run src/moex_dashboard/app.py
```

## Тесты

```bash
uv run pytest tests/ -v
```

## Структура проекта

```
src/moex_dashboard/
├── app.py                  # Streamlit entry point (auto-refresh 30s)
├── config.py               # ASSET_MAP, constants, tickers
├── models.py               # SpotQuote, FuturesContract, MarketSnapshot, Signal
├── data/
│   ├── moex_api.py         # MOEX ISS API wrapper (retry, parse)
│   ├── spot.py             # Spot currencies, indices, stocks
│   ├── futures.py          # FORTS futures loader
│   ├── rates.py            # RUSFAR, КС ЦБ
│   ├── perpetual.py        # Perpetual FX futures (prices, specs, candles)
│   └── snapshot.py         # MarketSnapshot builder
├── calc/
│   ├── arbitrage.py        # implied_rate, fair_value, basis, carry_premium
│   ├── cip.py              # CIP, si/eu parity, gold parity, cross-instrument
│   ├── stocks.py           # implied_dividend, dividend_yield
│   ├── funding.py          # Funding: calc_d, calc_funding, annualized
│   └── pipeline.py         # build_*_table() → pd.DataFrame
└── ui/
    ├── sidebar.py          # Sidebar: quotes, rates, timestamp
    ├── tab_arbitrage.py    # 8 sub-tabs: C&C, Reverse, Calendar, Cross-*, CIP, Funding
    ├── tab_relative.py     # 3 sub-tabs: Curve Shape, Calendar Commodity, Rate Spread
    ├── tab_curves.py       # Per-asset futures curves
    ├── tab_stocks.py       # Stocks carry, implied dividends
    ├── _arb_extras.py      # Cross-Gold, Cross-Instrument renders
    └── _styling.py         # Color formatting functions
data/                       # Скачанные JSON с оригинала (2026-02-23)
├── backtest_data.json      # Бэктест Преф/Обычка (3 пары, 627 недель, 2013-2026)
├── snapshot.json           # Полный снимок рынка (sector_signals, equities, и др.)
├── dividends.json          # Историческая база дивидендов
├── consensus.json          # Мультифакторный скоринг акций
├── declared_divs.json      # Объявленные дивиденды
├── corp_bonds.json         # Корп. облигации (~1800 штук)
├── openapi.json            # OpenAPI спец. основного API (порт 8503)
└── openapi_news.json       # OpenAPI спец. News API (порт 8098)
tests/
└── test_calc.py            # 23 tests for all calc formulas
scripts/
└── screenshot_dashboard.py # Playwright: автоскриншоты всех табов оригинала
screenshots/                # 25 скриншотов оригинального дашборда (2026-02-21)
screenshots_2026-02-23/     # 35 скриншотов всех табов (01_01 — 12_06)
devtools_dump_2026-02-23/   # DevTools дамп: API URLs, JS source, DOM, state
├── api_urls.txt            # 31 API-эндпоинт оригинала
├── source_code.txt         # JavaScript исходник
├── dom_structure.txt       # HTML-структура
├── js_state.txt            # Frontend state variables
└── websocket_messages.txt  # WebSocket (пусто — не используется)
```

## Скачанные данные с оригинала (data/)

23 февраля 2026 скачаны все доступные JSON-эндпоинты оригинального Packman Monitor:

```
data/
├── backtest_data.json   (99 KB)  — бэктест "Преф/Обычка" (3 пары + Portfolio)
├── snapshot.json        (403 KB) — полный снимок рынка (23 секции)
├── dividends.json       (70 KB)  — историческая база дивидендов
├── consensus.json       (36 KB)  — мультифакторный скоринг акций
├── declared_divs.json   (0.2 KB) — объявленные дивиденды (ex-date)
├── corp_bonds.json      (678 KB) — корпоративные облигации (~1800 штук)
├── openapi.json         (6 KB)   — OpenAPI 3.0 спецификация основного API (порт 8503)
└── openapi_news.json    (3 KB)   — OpenAPI спецификация News API (порт 8098)
```

**Источники:**
- Порт 8503: `/static/backtest_data.json`, `/api/snapshot`, `/static/dividends.json`, `/static/consensus.json`, `/static/declared_divs.json`, `/static/corp_bonds.json`, `/openapi.json`
- Порт 8098: `/openapi.json` (News API)

### Структура backtest_data.json

Бэктест стратегии "Преф/Обычка" — парный трейдинг привилегированных vs обычных акций.

```json
{
  "SBER/P": {
    "d": ["2013-09-30", "2013-10-07", ...],  // 627 недельных дат (12.4 года)
    "s": [3019425, 3016236, ...],             // equity curve стратегии
    "r": [3016018, 3018290, ...],             // бенчмарк
    "a": [3407, -2054, 9233, ...],            // альфа (недельная)
    "sharpe": 2.34,                            // Sharpe ratio
    "util": 48.6,                              // утилизация капитала (%)
    "alpha": 3554196,                          // кумулятивная альфа
    "alpha_ann": 9.6,                          // годовая альфа (%)
    "yrs": 12.4                                // период (лет)
  },
  "TATN/P": { ... },
  "RTKM/P": { ... },
  "Portfolio": { ... }
}
```

**Важно:** бэктест считается на сервере (бэкенд Packman Monitor), а НЕ в текущем коде. Наш Streamlit-дашборд только визуализирует готовый JSON. Алгоритм бэктеста не реализован локально.

**Инструменты:** SBER/P (Сбербанк), TATN/P (Татнефть), RTKM/P (Ростелеком)
**Период:** 2013–2026, 627 недель
**Sharpe портфеля:** 2.34, годовая альфа: 9.6%

### Структура snapshot.json — секторные данные

Массив `sector_signals` содержит 8 секторов:

```json
{
  "sector_signals": [
    {
      "code": "L1",
      "name": "Электроэн.",
      "date": "2026-02-23",
      "price": 1234.56,
      "m1": 2.3,           // 1-месячный моментум (%)
      "m3": 8.5,           // 3-месячный моментум (%) — ключевой для сигнала
      "m6": 15.2,
      "m12": 28.1,
      "signal": "LONG",    // LONG / SHORT / FLAT
      "today_chg": 0.45
    },
    ...
  ]
}
```

**8 секторов — стандартные отраслевые индексы MOEX:**

| Индекс MOEX | Сектор | Бумаг в индексе | Топ-3 по весу | URL |
|---|---|---|---|---|
| MOEXEU | Электроэнергетика | 14 | IRAO 14.8%, LSNGP 13.4%, MSNG 11.0% | moex.com/ru/index/MOEXEU |
| MOEXOG | Нефть и газ | 11 | GAZP 20.2%, LKOH 19.2%, NVTK 16.0% | moex.com/ru/index/MOEXOG |
| MOEXMM | Металлы и добыча | 15 | GMKN 15.7%, PLZL 14.6%, CHMF 12.5% | moex.com/ru/index/MOEXMM |
| MOEXFN | Финансы | 14 | VTBR 17.2%, T 16.0%, MOEX 15.1% | moex.com/ru/index/MOEXFN |
| MOEXCN | Потребительский | 17 | MGNT 16.1%, MDMG 13.4%, X5 12.8% | moex.com/ru/index/MOEXCN |
| MOEXTL | Телекоммуникации | 4 | MTSS 40.8%, RTKM 33.0%, MGTSP 19.2% | moex.com/ru/index/MOEXTL |
| MOEXTN | Транспорт | 5 | AFLT 29.2%, FLOT 29.0%, NMTP 17.6% | moex.com/ru/index/MOEXTN |
| MOEXCH | Химия | 4 | PHOR 39.8%, AKRN 31.8%, NKNC 20.1% | moex.com/ru/index/MOEXCH |

Packman Monitor не изобретает свою классификацию — использует стандартные отраслевые индексы Мосбиржи. Котировки и составы индексов доступны через MOEX ISS API (без авторизации):

**Котировки всех 8 секторных индексов (одним запросом):**
```
GET https://iss.moex.com/iss/engines/stock/markets/index/securities.json?securities=MOEXEU,MOEXOG,MOEXMM,MOEXFN,MOEXCN,MOEXTL,MOEXTN,MOEXCH&iss.only=marketdata&marketdata.columns=SECID,CURRENTVALUE,LASTCHANGE,LASTCHANGEPRCNT
```

**Состав конкретного индекса (тикеры + веса):**
```
GET https://iss.moex.com/iss/statistics/engines/stock/markets/index/analytics/MOEXEU.json?iss.only=analytics&analytics.columns=ticker,shortnames,weight&limit=100
```
Заменить `MOEXEU` на нужный код: MOEXOG, MOEXMM, MOEXFN, MOEXCN, MOEXTL, MOEXTN, MOEXCH.

**Историческая котировка индекса (для расчёта моментумов m1/m3/m6/m12):**
```
GET https://iss.moex.com/iss/history/engines/stock/markets/index/securities/MOEXEU.json?from=2025-02-23&till=2026-02-23&iss.only=history&history.columns=TRADEDATE,CLOSE
```

### Составы отраслевых индексов (на 23.02.2026)

**MOEXEU — Электроэнергетика (14 бумаг):**
IRAO 14.84%, LSNGP 13.39%, MSNG 11.03%, UPRO 8.85%, FEES 8.56%, MRKP 8.40%, HYDR 7.81%, MSRS 6.17%, MRKC 4.72%, MRKV 4.25%, MRKU 3.67%, OGKB 2.95%, TGKA 2.93%, ELFV 2.44%

**MOEXOG — Нефть и газ (11 бумаг):**
GAZP 20.18%, LKOH 19.20%, NVTK 16.01%, TATN 15.75%, ROSN 9.70%, SNGS 7.16%, SNGSP 6.27%, TATNP 2.78%, TRNFP 1.75%, BANEP 0.73%, RNFT 0.47%

**MOEXMM — Металлы и добыча (15 бумаг):**
GMKN 15.73%, PLZL 14.57%, CHMF 12.46%, RUAL 12.31%, NLMK 11.78%, MAGN 7.28%, ALRS 6.76%, VSMO 4.76%, ENPG 4.35%, UGLD 3.25%, SELG 2.45%, MTLR 1.35%, TRMK 1.21%, RASP 0.94%, MTLRP 0.80%

**MOEXFN — Финансы (14 бумаг):**
VTBR 17.19%, T 16.03%, MOEX 15.06%, SBER 12.29%, SVCB 8.32%, DOMRF 7.95%, CBOM 6.33%, BSPB 5.15%, RENI 2.91%, SBERP 2.37%, LEAS 2.07%, SFIN 2.05%, MBNK 1.27%, SPBE 1.00%

**MOEXCN — Потребительский (17 бумаг):**
MGNT 16.13%, MDMG 13.44%, X5 12.76%, RAGR 11.52%, LENT 9.74%, GEMC 6.14%, AQUA 4.21%, FIXR 4.12%, OZPH 3.87%, EUTR 3.43%, BELU 3.22%, PRMD 3.03%, VSEH 2.38%, APTK 1.91%, WUSH 1.77%, HNFG 1.18%, SVAV 1.16%

**MOEXTL — Телеком (4 бумаги):**
MTSS 40.83%, RTKM 33.03%, MGTSP 19.15%, RTKMP 6.98%

**MOEXTN — Транспорт (5 бумаг):**
AFLT 29.16%, FLOT 29.00%, NMTP 17.61%, FESH 16.89%, NKHP 7.34%

**MOEXCH — Химия (4 бумаги):**
PHOR 39.82%, AKRN 31.79%, NKNC 20.05%, NKNCP 8.34%

**Логика сигналов Sector Rotation:**
- Ранжирование по `m3` (3-месячный моментум)
- Top-2 → LONG, Bottom-2 → SHORT, остальные → FLAT
- Ребалансировка ежемесячная

Также `snapshot.json` содержит массив `equities` (251 акция) с полем `sector` — это привязка акций к секторам. Ещё 96 акций без сектора (мелкие/неликвидные).

### API-сервисы

| Сервис | URL | Описание |
|---|---|---|
| Основной дашборд | https://www.packmanmarkets.ru/ | Packman Monitor v2, все табы и данные |
| News API | https://www.packmanmarkets.ru/api/news/ | Перенесён с порта 8098 на основной домен. 11 каналов, 8074 сообщений |

News API на новом домене:
- `/api/news/feed?limit=50` — лента новостей (8074 сообщений, ~2100/день)
- `/api/news/stats` — статистика + top тикеры по упоминаниям
- `/api/news/channels` — 11 источников: Telegram-каналы + RSS (TASS, RBC, Interfax, Finam)
- `/api/news/search?q=SBER` — поиск по тикеру/тексту
- `/api/news/ticker/{ticker}` — 500 на новом домене (возможно баг)

**Полный каталог API (25+ endpoints) → см. `Packman_Portal_Features.md` раздел 4.**

## Файлы

| Файл | Описание |
|---|---|
| `MOEX_Dashboard_TZ.md` | Полное техническое задание (1632 строки) |
| `HOW_TO_EARN.md` | Руководство по стратегиям портала |
| `Packman_Portal_Features.md` | Каталог фич портала, GAP-анализ, API, конкуренты (февраль 2026) |
| `Codex_MOEX_Portal_HLD_LLD.md` | Архитектура: HLD/LLD, формулы, API маппинг |
| `Codex_MOEX_Portal_Compact_Mapping.md` | Компактный маппинг: экран → формула → API |
| `Codex_Учебник_Как_Работать_С_Порталом.md` | Playbook: сигнал → позиция → выход |
| `CLAUDE.md` | Этот файл — описание проекта и прогресс |

## Ключевые технологии

- **Python** + **Streamlit** — фронтенд/бэкенд
- **MOEX ISS API** — бесплатный REST API, без авторизации, задержка ~15 мин
- **pandas** — обработка данных
- **requests** — HTTP-запросы к API

## Ключевые формулы

| # | Формула | Суть |
|---|---|---|
| 1 | Implied Rate | `(Futures/Spot - 1) * 365/Days` — годовая ставка из фьючерса |
| 2 | Fair Value | `Spot * (1 + КС_ЦБ * Days/365)` — теоретическая цена фьючерса |
| 3 | Implied Dividend | `Fair Value - Futures` — ожидаемый дивиденд |
| 4 | Basis | `Futures - Spot` — контанго/бэквордация |
| 5 | Daily Carry | Аннуализированный базис в день |
| 6 | CIP Arb | `Impl_USDCNY = Si_futures / CR_futures` — покрытый процентный паритет |
| 7 | Si Parity | `USDRUB = CNYRUB * USDCNY` — валютный треугольник |
| 8 | Eu Parity | `EURRUB = USDRUB * EURUSD` — валютный треугольник |

---

## Оригинальный дашборд (Packman Monitor v2)

**URL:** https://www.packmanmarkets.ru/ (ранее http://188.68.222.166:8503)
**Название:** RUSSIAN MARKET PACKMAN MONITOR
**Технология:** Кастомный HTML/CSS/JS (НЕ стандартный Streamlit), WebSocket live-данные
**Обновление:** ~3 сек цикл, live-индикатор
**Скриншоты:** `screenshots/` (25 файлов, снято 2026-02-21 Playwright-скриптом)

### Глобальные элементы

**Header:** КС 15.5% | RUSFAR 15.30% | live | время МСК | UPD: серверное время

**Sidebar (всегда виден):**

| Раздел | Данные |
|---|---|
| Валюты | CNYRUB, EURRUB, EURUSD, USDCNY, USDRUB |
| Индексы | IMOEX, RTSI |
| RUSFAR | 1D, 1W, 2W, 1M, 3M (от 15.12% до 15.38%) |

**Footer:** Акций: 234 | Фьюч: 135 | ОФЗ: 60 | Last update timestamp

### Структура табов (13 табов, 25+ суб-табов) — обновлено 26.02.2026

```
1. Акции (t-stocks)
│  ├── Market Data (md-eq)      — ~250 акций, цены, объёмы, дивиденды, дисбаланс
│  ├── Dividend Arb (stocks)    — ~80 пар акция-фьючерс, carry, implied div
│  ├── Fundamentals (gf)        — 414 компаний, 69 метрик, МСФО/РСБУ (iframe /gf/)
│  ├── Consensus (cons)         — 124 акции, консенсус аналитиков
│  └── Volume (vol)             — аномалии объёмов (Algopack buy/sell)
│
2. Облигации (t-bonds)
│  ├── ОФЗ (md-ofz)             — 30 выпусков + интерактивная кривая доходности (2013-2026)
│  └── Корп. облигации (md-corp) — 500+ бумаг, scatter-plot, 6 фильтров, G-spread
│
3. Фьючерсы (t-futures)
│  ├── Market Data (md-fut)     — 270+ контрактов, VWAP, OI, дисбаланс, ГО
│  ├── Curves (curves)          — 36+ активов, 8 категорий (вкл. агро, крипто)
│  └── OI Физ/Юр (futoi)        — физики vs юрики, net позиции, графики
│
4. Арбитраж & RV (t-arbrv)
│  ├── Арбитраж
│  │   ├── Cash-and-Carry       — implied rate vs КС/RUSFAR
│  │   ├── Reverse C&C          — шорт спот + лонг фьючерс
│  │   ├── Calendar FX          — валютные календарные спреды
│  │   ├── Cross-Instrument     — big vs mini (MX/MXI, RI/RH)
│  │   ├── Cross-FX             — CR/Si/Eu треугольный арбитраж
│  │   ├── Cross-Gold           — GL vs GD, implied USDRUB
│  │   └── CIP Arb              — implied USDCNY из Si/CR
│  └── Relative Value
│      ├── Calendar Commodity   — товарные спреды
│      ├── Curve Shape          — контанго/бэквордация/смешанная
│      └── Rate Spread          — implied rate vs КС
│
5. Стратегии (t-strat)
│  ├── Преф/Обычка (pref)       — mean reversion, бэктест 12+ лет
│  ├── Сектор Ротация (sector)  — momentum L/S 8 секторов
│  ├── Momentum (mom)           — dual momentum scoreboard
│  └── Dividend Capture (div)   — Tier 1/2, ~8%/сделку
│
6. Фонды (t-funds)              — 500+ ПИФов + heatmap 100 крупнейших
│
7. Макро (t-macro)               — макро-индикаторы РФ, периоды 1Y-MAX
│
8. Календарь (t-cal)             — 6389 событий, 6 типов, 180 дней вперёд
```

**Подробное описание каждого таба → см. `Packman_Portal_Features.md` раздел 2.**

### Детали по табам

#### 1. Арбитраж

**Общий заголовок:** "АРБИТРАЖ — механизм конвергенции. Сходимость обеспечена экспирацией, треугольным соотношением или единым базовым активом."

**1.1 Cash-and-Carry** — основная таблица (~25-30 строк):
- Столбцы: Актив, Контракт, Экспирация, Дней, Спот, Фьюч, Implied Rate, Премия КС, Объём ₽, Сделки, Пр. RUSFAR
- Активы: валюты (Si, Eu, CR), индексы (MX, RI), товары (BR, NG, GD, SV), акции
- Цвет: зелёный = implied rate > бенчмарк, красный = ниже
- Внизу: секция "Арбитражные возможности" с лучшими парами

**1.2 Reverse C&C** — ~25-35 строк:
- Шорт спот + лонг фьючерс (зеркало C&C)
- Столбцы: Спот, Фьюч, Значения, Статус, Действие
- Много строк со статусом "Привлекательно"

**1.3 Calendar FX** — 14 строк (все комбинации Si/Eu/CR):
- Столбцы: Актив, Ближний, Дальний, Δ Rate, Абс.спред, Направление
- Лучшая ставка: Si-3.26/Si-6.26 = +9.91%
- Все направления: "Лонг бл./шорт дл." (контанго)

**1.4 Cross-Instrument** — два раздела:
- MX vs IMOEX, RI vs RH (индексные кроссы)
- Индексы MOEX на спот SPMEX (матрица)

**1.5 Cross-FX** — треугольный арбитраж CR/Si/Eu:
- Таблица ставок: CR Rate, Si Rate, Eu Rate, Max Δ по экспирациям
- Аномалия: Si 03.2026 = -4.60% (красный)
- Лучший профит: Si-CR 03.2026 = +8.54%
- Действия: "Лонг Si + Шорт CR + Лонг USDCNY" и т.п.

**1.6 Cross-Gold** — GL(руб) vs GD(долл):
- Impl.USDRUB из GL/GD vs Market USDRUB
- Расхождение растёт с дальностью: 03.2026 +0.21% → 12.2026 +6.72%
- Действие: "Шорт GL + Лонг GD + Лонг Si"

**1.7 CIP Arb** — Covered Interest Parity:
- Impl.USDCNY = Si/CR vs Spot USDCNY
- Forward premium: от -8.52% (03.2026) до +0.84% (03.2027)
- Лучший профит: USDCNY fwd 03.2026 = +6.81%
- Формула: `Fwd Premium = (Impl/Spot - 1) × 365/Дней`

**Общий паттерн арбитража:** Si (USDRUB) near-term (03.2026, 25 дней) аномально дёшев — это каскадирует через Cross-FX (+8.54%), CIP (+6.81%), Calendar FX (+9.91%).

#### 2. Relative Value

**2.1 Calendar Commodity:**
- Энергоносители (BR, NG): бэквордация (красные бары)
- Металлы (Gold, Silver, Pt, Pd): контанго (зелёные бары, 14-16% годовых для золота)
- Столбцы: Актив, контракты, spread, z-ann, визуальный бар, комментарий

**2.2 Curve Shape:**
- Классификация: КОНТАНГО / СМЕШАННАЯ по классам активов
- Валюты: все в контанго (USDRUB +11.50, EURRUB +7.66, CNYRUB +1.52)
- Энергия: смешанная, Металлы: преимущественно контанго

**2.3 Rate Spread:**
- Implied rate vs key rate для ~30+ акционных фьючерсов
- Дивидендные пометки в комментариях

#### 3. Div Arb & Carry

- ~40+ пар акция-фьючерс
- Столбцы: Тикер, Акция(цена), Фьючерс(цена), Экспирация, Базис, Базис%, Див ожид, Див дата, Базис-Див, Carry Ann%
- Яркие зелёные/красные фоны для сигналов
- Охват: Газпром, Сбербанк, Лукойл, Роснефть, НорНик, Татнефть, Сургут, Северсталь, МТС, Яндекс, Магнит, НЛМК, ВТБ, Полюс, Алроса, TCS и др.

#### 4. Market Data

**4.1 Акции** — 234 бумаги:
- Столбцы: Тикер, Название, Листинг, Сектор, Лот, Цена, Оборот, %1Д, %1Н, Дата див, Размер див, Див.дох%

**4.2 Корп.бонды** — 1805 бумаг, 836 эмитентов:
- Средний YTM: 21.38%, средняя дюрация: 1.3 лет
- Scatter plot: Доходность vs Дюрация
- Столбцы: Выпуск, Рейт., Лист., Вал., Цена%, YTM%, ОФЗ%, G-спред, Дюр.лет, Купон, Погашение, Оборот
- Фильтры: Листинг, Валюта, Тип, Рейтинг, Сектор, Эмитент

**4.3 ОФЗ** — 60 выпусков:
- Средний YTM: 14.38% (ниже КС → рынок ждёт снижения ставки)
- Средняя дюрация: ~4.4 лет
- Столбцы: Выпуск, Цена, Купон, НКД, Дата купона, Дата погашения, Дюрация, YTM%, Оборот, Сделки

**4.4 Фьючерсы** — 135 контрактов (69 активных):
- Общий объём: ~20.7 млн контрактов
- Столбцы: Тикер, Базовый актив, Экспирация, Лот, Цена, Расчётная, Изменение, %Изм, Объём, OI

#### 5. Консенсус Акции

- 327 акций, мультифакторный консенсус-скоринг
- Столбцы: Тикер, Название, Сектор, Цена, MCap, факторные скоры, %1Д/1Н/1М/3М/6М/12М, Консенсус
- Все основные сектора MOEX

#### 6. Стратегии

**6.1 Преф/Обычка:**
- Парный трейдинг преф vs обычка (Сбербанк, Сургут, Татнефть, Ростелеком, Башнефть, Мечел, Транснефть)
- Бэктест 2013-2026 с реинвестированием, графики equity curve
- Sharpe: от 1.03 до 3.3x

**6.2 Сектор Ротация:**
- Momentum L/S: Long top-2 по 3M, Short bottom-2, ребал ежемесячно
- Бэктест: Sharpe 1.01, +18.2%/yr (15 лет)
- 8 секторов: Электроэн., Металлы, Телеком, Потреб., Финансы, Транспорт, Химия, Нефтегаз
- Текущие сигналы: LONG Электроэн.+Металлы, SHORT Химия+Нефтегаз

**6.3 Momentum:**
- Cross-Asset Momentum Scoreboard
- Dual momentum: Absolute (3M>0) + Relative (top-3)
- Сигналы: STRONG BUY / BUY / HOLD-EXIT / AVOID
- Активы: секторные индексы, индивидуальные акции, товары (золото), индексы

**6.4 Дивиденды:**
- Dividend Capture Calendar & Signals
- Tier 1: D+1..6, 100% Win Rate (подтверждённые)
- Tier 2: D+1..5, ожидание (ожидаемые)
- ~25 бумаг, зелёные бары сигналов

#### 7. Макро

- Интерактивный график макро-индикаторов РФ
- Dropdown для выбора индикатора (КС ЦБ и др.)
- Кнопки периода: 1Y, 3Y, 5Y, 10Y, MAX
- КС ЦБ: 62 точки, 2013-01-01 — 2025-12-19, текущая 15.5%, delta -0.50

#### 8. Объёмы

- Аномалии торговой активности по деривативам
- Столбцы: Инструмент, Тикер, Объём, Ср.объём, Ratio, Аномалия%
- Heatmap-раскраска: зелёный = объём выше среднего
- 30+ фьючерсов: акции, индексы, валюты, товары

#### 9. OI Физ/Юр

- Open Interest: физики (retail) vs юрики (institutional)
- Столбцы: Инструмент, OI, Физ Long/Short, Юр Long/Short, Net Физ, Net Юр, CR, Сигнал, S1, MR, OL
- Аналог CFTC COT-отчётов для MOEX
- Квантовые сигналы на основе позиционирования

#### 10. Кривые

- Term Structure: интерактивные фьючерсные кривые
- Фильтры: Класс (Все), Актив (dropdown)
- Сравнение: Today, -1D, -1W, -1M, -1Y
- Визуализация контанго/бэквордации по экспирациям

### Отличия от нашей реализации (обновлено 26.02.2026)

| Функция | Packman Monitor v2 | Наша реализация |
|---|---|---|
| Табов | 13 | 4 |
| Суб-табов | 25+ | 12 (8+3+1) |
| Технология | Кастомный HTML/JS, FastAPI | Streamlit |
| Акции | ~250 + фундаментал (414 компаний, 69 метрик) | Только спот |
| Фонды | 500+ ПИФов + heatmap | Нет |
| Календарь | 6389 событий (купоны, погашения, ЦБ, дивиденды) | Нет |
| Стратегии | 4 суб-таба (momentum, rotation, pref/com, div capture) | Нет |
| Макро | Интерактивные графики | Нет |
| OI Физ/Юр | Retail vs institutional + графики истории | Нет |
| Консенсус | 124 акции, target, rec, мультипликаторы | Нет |
| Корп.бонды | 500+ бумаг с G-spread, scatter, 6 фильтров | Нет |
| ОФЗ | 30 выпусков + интерактивная кривая (2013-2026) | Нет |
| Кривые | 36+ активов, 8 категорий (вкл. агро, крипто) | Нет |
| Цветовая раскраска | Полная (зелёный/красный фоны, heatmaps, бары) | Частичная |
| Бэктесты | Да (661 неделя, Sharpe, equity curves) | Нет |
| Live обновление | Polling 3 сек с ETag | Streamlit auto-refresh 30 сек |
| Anti-debug | Да (DevTools, F12, copy блокированы) | Нет |
| Mobile | Responsive (sidebar hides < 768px) | Нет |
| Funding tab | Нет | Да (perpetual futures) |

## Возможные развития / Инкубатор

### 1. Аналог терминала для US-рынка

**Проблема:** На US-рынке нет single-stock futures (OneChicago закрылась в 2020). Cash-and-Carry арбитраж на отдельных акциях невозможен. Базис-трейдинг на индексах (ES vs SPY) давно забит HFT до десятых bp.

**Что возможно вместо арбитража фьючерсов:**
- Put-call parity (синтетические форварды из опционов) — сотни ликвидных тикеров
- ETF vs NAV арбитраж
- ADR vs домашняя биржа (BABA NYSE vs HK)
- Crypto basis (CME BTC futures vs spot)

**Источники данных для US-терминала:**

| Данные | Источник | Лимит (бесплатно) |
|---|---|---|
| Фундаментал | SEC EDGAR XBRL | Безлимит, 10 req/сек. Первоисточник, парсинг XBRL сложный |
| Фундаментал (готовый JSON) | FMP (Financial Modeling Prep) | 250 req/день. S&P 500 = 2 дня на полный обход |
| Макро | FRED (St. Louis Fed) | 800K+ серий, бесплатно. Лучший макро-API в мире |
| Yield curve | US Treasury API | Ежедневно, бесплатно |
| OI / позиционирование | CFTC COT Reports | Еженедельно, бесплатно |
| Реалтайм котировки | Finnhub | 60 req/мин + WebSocket. Лучший free tier |
| Реалтайм котировки | Polygon/Massive | 5 req/мин бесплатно (только EOD). Реалтайм от $30/мес |
| Новости + консенсус | Finnhub | Free tier, с тикер-тэгами |
| Фонды | SEC N-PORT | Квартальные портфели всех mutual funds/ETFs |

**Архитектура MVP:**
```
SEC EDGAR XBRL  ──→  фундаментал (крон раз/день)
FRED API        ──→  макро (ежедневно)
Finnhub         ──→  котировки (WebSocket) + новости + консенсус + календарь
CFTC COT        ──→  OI / позиционирование (еженедельно)
US Treasury     ──→  yield curve (ежедневно)
```

**Вывод:** фундаментал + макро + новости = бесплатно. Реалтайм котировки: Finnhub free (60 req/мин) хватит для MVP. Для продакшена — FMP $19/мес (безлимит + WebSocket).

### 2. Арбитраж на KASE (Казахстанская биржа)

**Базовая ставка Нацбанка Казахстана: 18%** (февраль 2026) → теоретический базис фьючерсов ~12-16% годовых.

**Что торгуется на KASE (деривативы):**

| Фьючерс | Код | Базовый актив |
|---|---|---|
| Халык Банк (НБК) | HSBK-6.26 | Акции |
| Казатомпром | KZAP-6.26 | Акции |
| Индекс KASE | KX-6.26 | Индекс |
| USD/KZT | US-6.26 | Валюта |
| RUB/KZT | RU-6.26 | Валюта |

Всего 5 инструментов, беспоставочные (расчётные). Торги 10:00–17:30 Астана.

**Ликвидность (2025):** $18.3M за весь год (< 0.1% оборота KASE). Для сравнения MOEX FORTS делает столько за минуты. Но для мелкого капитала ($1-5K) — проскальзывание не критично.

**Потенциал:** рынок пуст (нет алгоритмов, нет конкуренции), ставка высокая (18%), базис должен быть жирным. Вопрос — есть ли кто по другую сторону стакана.

**Доступ к данным:**

| Канал | Что | Для кого |
|---|---|---|
| KASE Mobile (приложение) | Котировки акций + деривативов, бесплатно | Все — быстро проверить стакан |
| Freedom Finance (Tradernet) | WebSocket API: `wsbeta.tradernet.ru`, REST: `tradernet.ru/api/`, Python SDK на PyPI | Клиенты брокера |
| KASE ASTS Bridge / FIX 4.4 | Прямое подключение к торговой системе (та же ASTS что на MOEX) | Только члены биржи |
| STrade | Веб-терминал KASE через брокера | Клиенты брокеров |

**Публичного REST API у KASE нет** (в отличие от MOEX ISS). Всё — через брокеров.

**Брокеры для деривативов:** Freedom Finance KZ (fbroker.kz), Halyk Finance. Для фьючерсов нужен статус Professional Customer.

**Следующий шаг:** скачать KASE Mobile → посмотреть стакан фьючерсов HSBK-6.26 и KZAP-6.26. Если бид-аск < 3% и базис > 18% годовых → есть арбитраж.

### 3. Источники данных Packman Monitor

Результаты анализа API оригинала (26.02.2026):

**Фундаментал** (`/gf/api/fundamental/{ticker}`): 467 тикеров, до 69 метрик, МСФО/РСБУ, 5 лет + LTM. Источники: Smart-Lab (IR-рейтинги, "Присутствие на смартлабе"), e-disclosure.ru / раскрытие.рф (МСФО/РСБУ). Обновляется по крону (не реалтайм).

**Консенсус** (`/static/consensus.json`): 151 акция, target, rec (1-3), sales, EBITDA, P/E, ROE, дивиденды. Поле `dps_src: "dohod"` → источник dohod.ru. Статический файл.

**Новости** (`/api/news/feed`): 11 каналов (4 RSS: ТАСС, РБК, Интерфакс, Финам + 7 Telegram через Bot API). 8000+ сообщений, ~2300/день. Авто-тэгирование тикерами. Полнотекстовый поиск. На сайте отображение сломано после переезда на домен (API работает, фронтенд — нет).

## Источник

Оригинальный дашборд: **RUSSIAN MARKET PACKMAN MONITOR** на https://www.packmanmarkets.ru/ (ранее VPS порт 8503), кастомный HTML/JS с WebSocket, данные из MOEX ISS API в реальном времени.
