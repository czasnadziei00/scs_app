import json
import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


# ------------------------------------------------------------
# 1. SCS 3.0 — scoring trendu
# ------------------------------------------------------------
def calc_scs(ohlc_15m, ohlc_60m, ohlc_240m):
    score = 0

    def trend_points(v):
        if not v:
            return 0
        if "↑" in v:
            return 2
        if "↓" in v:
            return -2
        return 0

    def momentum_points(v):
        if not v or "%" not in v:
            return 0
        try:
            val = float(v.replace("↑", "").replace("↓", "").replace("%", "").strip())
            if val > 0.30:
                return 2
            if val < -0.30:
                return -2
        except:
            return 0
        return 0

    score += trend_points(ohlc_15m)
    score += trend_points(ohlc_60m)
    score += trend_points(ohlc_240m)

    score += momentum_points(ohlc_15m)
    score += momentum_points(ohlc_60m)
    score += momentum_points(ohlc_240m)

    ups = [("↑" in str(ohlc_15m)), ("↑" in str(ohlc_60m)), ("↑" in str(ohlc_240m))]
    if all(ups):
        score += 4
    downs = [("↓" in str(ohlc_15m)), ("↓" in str(ohlc_60m)), ("↓" in str(ohlc_240m))]
    if all(downs):
        score -= 4

    if ohlc_15m and ohlc_60m:
        if "↑" in ohlc_15m and "↑" in ohlc_60m:
            score += 2
        if "↓" in ohlc_15m and "↓" in ohlc_60m:
            score -= 2

    return max(0, min(20, score))


# ------------------------------------------------------------
# 2. Automatyczne widełki i TP
# ------------------------------------------------------------
def auto_levels(last_price):
    if not last_price:
        return None
    try:
        p = float(last_price)
    except:
        return None

    buy_zone_low = round(p * 0.995, 2)
    buy_zone_high = round(p * 1.005, 2)
    tp1 = round(p * 1.01, 2)
    tp2 = round(p * 1.02, 2)
    tp3 = round(p * 1.03, 2)

    return buy_zone_low, buy_zone_high, tp1, tp2, tp3


# ------------------------------------------------------------
# 3. Wczytanie / zapis historii
# ------------------------------------------------------------
def load_history():
    with open("history.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)


# ------------------------------------------------------------
# 4. API do aktualizacji pól
# ------------------------------------------------------------
@app.route("/update", methods=["POST"])
def update():
    data = request.json
    ticker = data.get("ticker")
    field = data.get("field")
    value = data.get("value")

    history = load_history()

    if ticker not in history:
        history[ticker] = {}

    # zapis last_price + historia cen
    if field == "last_price":
        try:
            value_float = float(value)
        except:
            return jsonify({"status": "error", "msg": "Nieprawidłowa cena"}), 400

        history[ticker]["last_price"] = value_float

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "history" not in history[ticker]:
            history[ticker]["history"] = []
        history[ticker]["history"].append({
            "price": value_float,
            "time": ts
        })
    else:
        history[ticker][field] = value

    save_history(history)
    return jsonify({"status": "ok"})


# ------------------------------------------------------------
# 5. Klasa wiersza wg sygnału
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
    ohlc_15m = data.get("ohlc_15m")
    ohlc_60m = data.get("ohlc_60m")
    ohlc_240m = data.get("ohlc_240m")

    scs = calc_scs(ohlc_15m, ohlc_60m, ohlc_240m)

    levels = auto_levels(last_price)
    if levels:
        buy_zone_low, buy_zone_high, tp1, tp2, tp3 = levels
    else:
        buy_zone_low = buy_zone_high = tp1 = tp2 = tp3 = None

    entry = buy_zone_low

    signal = "czekaj"

    if tp3 and last_price:
        try:
            if float(last_price) > float(tp3):
                new_struct = auto_levels(last_price)
                if new_struct:
                    buy_zone_low, buy_zone_high, tp1, tp2, tp3 = new_struct
                    entry = buy_zone_low
                signal = "trend trwa — nowa struktura"
        except:
            pass

    try:
        if buy_zone_low and buy_zone_high and last_price:
            lp = float(last_price)
            if float(buy_zone_low) <= lp <= float(buy_zone_high):
                signal = "BUY ZONE"
    except:
        pass

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
        "buy_zone_low": buy_zone_low,
        "buy_zone_high": buy_zone_high,
        "buy_zone": f"{buy_zone_low} – {buy_zone_high}" if buy_zone_low else "-",
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
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

    def sort_key(x):
        in_buy = "BUY ZONE" in str(x["signal"])
        return (not in_buy, x["entry"] is None, x["entry"])

    results.sort(key=sort_key)

    return render_template("index.html", results=results, get_row_class=get_row_class)


# ------------------------------------------------------------
# 8. Start
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
