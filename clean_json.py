import json

INPUT = "history.json"
OUTPUT = "history_clean.json"

REMOVE_FIELDS = [
    "history",
    "signal",
    "buy_zone",
    "tp1",
    "tp2",
    "tp3"
]

DEFAULT_FIELDS = {
    "last_price": None,
    "ohlc_15m": None,
    "ohlc_60m": None,
    "ohlc_240m": None,
    "entry": None,
    "scs": 0
}

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

cleaned = {}

for name, item in data.items():
    new_item = {}

    # usuń stare pola
    for k, v in item.items():
        if k not in REMOVE_FIELDS:
            new_item[k] = v

    # dodaj brakujące pola
    for k, v in DEFAULT_FIELDS.items():
        if k not in new_item:
            new_item[k] = v

    cleaned[name] = new_item

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(cleaned, f, indent=4, ensure_ascii=False)

print("✔ Zrobione! Nowy plik zapisany jako:", OUTPUT)
