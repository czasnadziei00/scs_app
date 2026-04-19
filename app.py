import json
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# ------------------------------------------------------------
# 1. Pobieranie ceny ze Stooq
# ------------------------------------------------------------
def get_price(ticker):
    try:
        url = f"https://stooq.com/q/l/?s={ticker}.pl&i=d"
        r = requests.get(url, timeout=5)
        data = r.text.split(",")
        price = float(data[6]) if len(data) > 6 else None
        return price
    except:
        return None

# ------------------------------------------------------------
# 2. Nowa struktura po wybiciu TP3
# ------------------------------------------------------------
def update_structure_after_tp3(last_price):
    buy_zone_low = round(last_price * 0.995, 2)
    buy_zone_high = round(last_price * 1.005, 2)

    entry = buy_zone_low

    tp1 = round(last_price * 1.01, 2)
    tp2 = round(last_price * 1.02, 2)
    tp3 = round(last_price * 1.03, 2)

    return {
        "buy_zone_low": buy_zone_low,
        "buy_zone_high": buy_zone_high,
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3
    }

# ------------------------------------------------------------
# 3. Wczytanie historii
# ------------------------------------------------------------
def load_history():
    with open("history.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ------------------------------------------------------------
# 4. Zapis zmian OHLC / TP / BUY ZONE
# ------------------------------------------------------------
@app.route("/update", methods=["POST"])
def update():
    data = request.json

    with open("history.json", "r", encoding="utf-8") as f:
        history = json.load(f)

    ticker = data["ticker"]
    field = data["field"]
    value = data["value"]

    history[ticker][field] = value

    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    return {"status": "ok"}

# ------------------------------------------------------------
# 5. Logika sygnałów
# ------------------------------------------------------------
def process_ticker(name, data):
    last_price = data.get("last_price")
    entry = data.get("entry")
    ohlc_15m = data.get("ohlc_15m")
    ohlc_60m = data.get("ohlc_60m")
    ohlc_240m = data.get("ohlc_240m")
    scs = data.get("scs", 0)

    buy_zone_low = data.get("buy_zone_low")
    buy_zone_high = data.get("buy_zone_high")
    tp1 = data.get("tp1")
    tp2 = data.get("tp2")
    tp3 = data.get("tp3")

    ticker = name.split("(")[-1].replace(")", "")
    price = get_price(ticker)
    if price:
        last_price = price

    signal = "czekaj"

    # ------------------------------------------------------------
    # LOGIKA: wybicie TP3 → nowa struktura
    # ------------------------------------------------------------
    if tp3 and last_price:
        if last_price > tp3:
            new_struct = update_structure_after_tp3(last_price)

            buy_zone_low = new_struct["buy_zone_low"]
            buy_zone_high = new_struct["buy_zone_high"]
            entry = new_struct["entry"]
            tp1 = new_struct["tp1"]
            tp2 = new_struct["tp2"]
            tp3 = new_struct["tp3"]

            signal = "trend trwa — nowa struktura"

    # BUY ZONE
    if buy_zone_low and buy_zone_high and last_price:
        if buy_zone_low <= last_price <= buy_zone_high:
            signal = "BUY ZONE"

    # TP
    if tp1 and last_price and last_price >= tp1:
        signal = "TP1"
    if tp2 and last_price and last_price >= tp2:
        signal = "TP2"
    if tp3 and last_price and last_price >= tp3:
        signal = "TP3 — możliwe wybicie"

    return {
        "name": name,
        "price": last_price,
        "scs": scs,
        "m15": ohlc_15m,
        "m60": ohlc_60m,
        "m240": ohlc_240m,
        "buy_zone": f"{buy_zone_low} – {buy_zone_high}" if buy_zone_low else "-",
        "entry": entry,
        "tp": f"{tp1} / {tp2} / {tp3}" if tp1 else "-",
        "signal": signal
    }

# ------------------------------------------------------------
# 6. Routing
# ------------------------------------------------------------
@app.route("/")
def index():
    history = load_history()
    results = []

    for name, data in history.items():
        results.append(process_ticker(name, data))

    return render_template("index.html", results=results)

# ------------------------------------------------------------
# 7. Start
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)