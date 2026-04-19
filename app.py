import json
from flask import Flask, render_template, request

app = Flask(__name__)

# ------------------------------------------------------------
# 1. SCS 3.0 — profesjonalny scoring trendu
# ------------------------------------------------------------
def calc_scs(ohlc_15m, ohlc_60m, ohlc_240m):
    score = 0

    # Trend kierunkowy
    def trend_points(v):
        if not v:
            return 0
        if "↑" in v:
            return 2
        if "↓" in v:
            return -2
        return 0

    score += trend_points(ohlc_15m)
    score += trend_points(ohlc_60m)
    score += trend_points(ohlc_240m)

    # Momentum
    def momentum_points(v):
        if not v or "%" not in v:
            return 0
        try:
            val = float(v.replace("↑", "").replace("↓", "").replace("%", ""))
            if val > 0.30:
                return 2
            if val < -0.30:
                return -2
        except:
            return 0
        return 0

    score += momentum_points(ohlc_15m)
    score += momentum_points(ohlc_60m)
    score += momentum_points(ohlc_240m)

    # Zgodność trendów
    dirs = [("↑" in str(ohlc_15m)), ("↑" in str(ohlc_60m)), ("↑" in str(ohlc_240m))]
    if all(dirs):
        score += 4
    dirs = [("↓" in str(ohlc_15m)), ("↓" in str(ohlc_60m)), ("↓" in str(ohlc_240m))]
    if all(dirs):
        score -= 4

    # Sekwencja świec
    if ohlc_15m and ohlc_60m:
        if "↑" in ohlc_15m and "↑" in ohlc_60m:
            score += 2
        if "↓" in ohlc_15m and "↓" in ohlc_60m:
            score -= 2

    return max(0, min(20, score))


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
# 4. Zapis zmian
# ------------------------------------------------------------
@app.route("/update", methods=["POST"])
def update():
    data = request.json

    with open("history.json", "r", encoding="utf-8") as f:
        history = json.load(f)

    ticker = data["ticker"]
    field = data["field"]
    value = data["value"]

    if ticker not in history:
        history[ticker] = {}

    history[ticker][field] = value

    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    return {"status": "ok"}

# ------------------------------------------------------------
# 5. Kolorowanie wierszy
# ------------------------------------------------------------
def get_row_class(signal):
    if not signal:
        return ""
    s = signal.upper()
    if "BUY ZONE" in s:
        return "row-buyzone"
    if "TP3" in s:
        return "row-tp3"
    if "TP2" in s:
        return "row-tp2"
    if "TP1" in s:
        return "row-tp1"
    if "NOWA STRUKTURA" in s or "TREND TRWA" in s:
        return "row-newtrend"
    return ""

# ------------------------------------------------------------
# 6. Logika sygnałów
# ------------------------------------------------------------
def process_ticker(name, data):
    last_price = data.get("last_price")
    entry = data.get("entry")
    ohlc_15m = data.get("ohlc_15m")
    ohlc_60m = data.get("ohlc_60m")
    ohlc_240m = data.get("ohlc_240m")

    # SCS 3.0
    scs = calc_scs(ohlc_15m, ohlc_60m, ohlc_240m)

    buy_zone_low = data.get("buy_zone_low")
    buy_zone_high = data.get("buy_zone_high")
    tp1 = data.get("tp1")
    tp2 = data.get("tp2")
    tp3 = data.get("tp3")

    signal = "czekaj"

    # LOGIKA: wybicie TP3 → nowa struktura
    if tp3 and last_price:
        try:
            if float(last_price) > float(tp3):
                new_struct = update_structure_after_tp3(float(last_price))

                buy_zone_low = new_struct["buy_zone_low"]
                buy_zone_high = new_struct["buy_zone_high"]
                entry = new_struct["entry"]
                tp1 = new_struct["tp1"]
                tp2 = new_struct["tp2"]
                tp3 = new_struct["tp3"]

                signal = "trend trwa — nowa struktura"
        except:
            pass

    # BUY ZONE
    try:
        if buy_zone_low and buy_zone_high and last_price:
            if float(buy_zone_low) <= float(last_price) <= float(buy_zone_high):
                signal = "BUY ZONE"
    except:
        pass

    # TP
    try:
        if tp1 and last_price and float(last_price) >= float(tp1):
            signal = "TP1"
        if tp2 and last_price and float(last_price) >= float(tp2):
            signal = "TP2"
        if tp3 and last_price and float(last_price) >= float(tp3):
            signal = "TP3 — możliwe wybicie"
    except:
        pass

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
# 7. Routing
# ------------------------------------------------------------
@app.route("/")
def index():
    history = load_history()
    results = []

    for name, data in history.items():
        results.append(process_ticker(name, data))

    results.sort(key=lambda x: (x["entry"] is None, x["entry"]), reverse=True)

    return render_template("index.html", results=results, get_row_class=get_row_class)

# ------------------------------------------------------------
# 8. Start
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
