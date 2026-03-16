"""Configuration: API endpoints, asset mappings, constants."""

BASE_URL = "https://iss.moex.com/iss"
CACHE_TTL_SECONDS = 30
REQUEST_TIMEOUT = 10
MAX_RETRIES = 2

# КС ЦБ — update manually when CBR changes the rate
# https://www.cbr.ru/hd_base/KeyRate/
KEY_RATE = 0.21  # 21% as of 2025-02-14

# Futures asset code (ASSETCODE from ISS API) → spot mapping
# price_divisor: divide LAST by this to get per-unit price comparable to spot
ASSET_MAP = {
    # Currencies — LAST is in RUB per lot, divide by lot volume to get per-unit
    "Si": {
        "spot_secid": "USD000UTSTOM",
        "name": "USDRUB",
        "market": "currency",
        "board": "CETS",
        "price_divisor": 1000,  # LAST=76799 → 76.799 RUB/USD
    },
    "CNY": {
        "spot_secid": "CNYRUB_TOM",
        "name": "CNYRUB",
        "market": "currency",
        "board": "CETS",
        "price_divisor": 1,  # LAST=11.150 → already per-CNY
    },
    "Eu": {
        "spot_secid": "EUR_RUB__TOM",
        "name": "EURRUB",
        "market": "currency",
        "board": "CETS",
        "price_divisor": 1000,  # LAST=90660 → 90.66 RUB/EUR
    },
    # CR is the MOEX ASSETCODE for CNYRUB futures (CRH6, CRM6, etc.)
    "CR": {
        "spot_secid": "CNYRUB_TOM",
        "name": "CNYRUB",
        "market": "currency",
        "board": "CETS",
        "price_divisor": 1,  # LAST already per-CNY
    },
    # Indices — MIX/RTS quoted in points*100, MXI already in index value
    "MIX": {
        "spot_secid": "IMOEX",
        "name": "IMOEX",
        "market": "index",
        "board": None,
        "price_divisor": 100,  # LAST=281850 → 2818.50
    },
    "MXI": {
        "spot_secid": "IMOEX",
        "name": "IMOEX (mini)",
        "market": "index",
        "board": None,
        "price_divisor": 1,  # LAST=2818.7 → already index value
    },
    "RTS": {
        "spot_secid": "RTSI",
        "name": "RTSI",
        "market": "index",
        "board": None,
        "price_divisor": 100,  # LAST=115760 → 1157.60
    },
    # Commodities — no spot on MOEX, used in Relative Value tab
    "BR": {"spot_secid": None, "name": "Brent", "market": "commodity", "board": None, "price_divisor": 1},
    "NG": {"spot_secid": None, "name": "Natural Gas", "market": "commodity", "board": None, "price_divisor": 1},
    "GD": {"spot_secid": None, "name": "Gold (USD)", "market": "commodity", "board": None, "price_divisor": 1},
    "GL": {"spot_secid": None, "name": "Gold (RUB)", "market": "commodity", "board": None, "price_divisor": 1},
    "SV": {"spot_secid": None, "name": "Silver", "market": "commodity", "board": None, "price_divisor": 1},
    "PT": {"spot_secid": None, "name": "Platinum", "market": "commodity", "board": None, "price_divisor": 1},
    "PD": {"spot_secid": None, "name": "Palladium", "market": "commodity", "board": None, "price_divisor": 1},
    # Stock futures — spot on TQBR board
    "HD": {"spot_secid": "HEAD", "name": "HeadHunter", "market": "stock", "board": "TQBR", "price_divisor": 1},
    "PS": {"spot_secid": "POSI", "name": "Positive Tech", "market": "stock", "board": "TQBR", "price_divisor": 1},
    "AL": {"spot_secid": "ALRS", "name": "АЛРОСА", "market": "stock", "board": "TQBR", "price_divisor": 100},
    "AK": {"spot_secid": "AFKS", "name": "АФК Система", "market": "stock", "board": "TQBR", "price_divisor": 100},
    "AF": {"spot_secid": "AFLT", "name": "Аэрофлот", "market": "stock", "board": "TQBR", "price_divisor": 100},
    "SR": {"spot_secid": "SBER", "name": "Сбербанк", "market": "stock", "board": "TQBR", "price_divisor": 100},
    "GZ": {"spot_secid": "GAZP", "name": "Газпром", "market": "stock", "board": "TQBR", "price_divisor": 100},
    "LK": {"spot_secid": "LKOH", "name": "Лукойл", "market": "stock", "board": "TQBR", "price_divisor": 1},
    "RI": {"spot_secid": "ROSN", "name": "Роснефть", "market": "stock", "board": "TQBR", "price_divisor": 100},
    "VK": {"spot_secid": "VKCO", "name": "VK", "market": "stock", "board": "TQBR", "price_divisor": 100},
    "WU": {"spot_secid": "WUSH", "name": "Whoosh", "market": "stock", "board": "TQBR", "price_divisor": 1},
    "X5": {"spot_secid": "X5", "name": "X5 Group", "market": "stock", "board": "TQBR", "price_divisor": 1},
}

# Spot securities we need to fetch
SPOT_CURRENCIES = ["USD000UTSTOM", "CNYRUB_TOM", "EUR_RUB__TOM"]
SPOT_INDICES = ["IMOEX", "RTSI"]

# Stock spot securities — extracted from stock entries in ASSET_MAP
STOCK_SECURITIES = [
    v["spot_secid"]
    for v in ASSET_MAP.values()
    if v["market"] == "stock" and v["spot_secid"] is not None
]

# Display names for spots
SPOT_NAMES = {
    "USD000UTSTOM": "USDRUB",
    "CNYRUB_TOM": "CNYRUB",
    "EUR_RUB__TOM": "EURRUB",
    "IMOEX": "IMOEX",
    "RTSI": "RTSI",
    # Stocks — secid equals display name
    **{secid: secid for secid in STOCK_SECURITIES},
}

# Futures expiry month codes
MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}

