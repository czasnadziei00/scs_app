import json
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

HISTORY_FILE = "history.json"


# -------------------------
# PLIK Z DANYMI
# -------------------------
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)


# -------------------------
# LOGIKA TRENDÓW
# -------------------------
def trend_from_ohlc(ohlc):
    if not ohlc or any(k not in ohlc or ohlc[k] is None for k in ["o", "c"]):
        return "-"
    o = float(ohlc["o"])
    c = float(ohlc["c"])
    if c > o:
        return "UP"
    elif c < o:
        return "DOWN"
    else:
        return "FLAT"


def trend_icon(trend):
    if trend == "UP":
        return '<span style="color:#00ff00;">▲</span>'
    if trend == "DOWN":
        return '<span style="color:#ff4444;">▼</span>'
    if trend == "FLAT":
        return '<span style="color:#aaaaaa;">■</span>'
    return '<span style="color:#555555;">-</span>'


# -------------------------
# SCS z trendów (setup score)
# -------------------------
def compute_scs_from_trends(t15, t60, t240):
    score = 0
    if t15 == "UP":
        score += 4
    if t60 == "UP":
        score += 6
    if t240 == "UP":
        score += 10
    if t15 == "DOWN":
        score -= 4
    if t60 == "DOWN":
        score -= 6
    if t240 == "DOWN":
        score -= 10
    return score


# -------------------------
# BUY ZONE + WIDEŁKI (v1)
# -------------------------
def compute_buy_zone_and_widely(ohlc_15m):
    if not ohlc_15m or any(k not in ohlc_15m or ohlc_15m[k] is None for k in ["l", "c"]):
        return "NO", None, None
    low = float(ohlc_15m["l"])
    close = float(ohlc_15m["c"])
    low_wide = low * 1.002
    high_wide = low * 1.004
    buy_zone = "YES" if close <= low_wide else "NO"
    return buy_zone, low_wide, high_wide


# -------------------------
# TP1 / TP2 / TP3
# -------------------------
def compute_tps(entry):
    if entry is None:
        return None, None, None
    entry = float(entry)
    tp1 = entry * 1.01
    tp2 = entry * 1.02
    tp3 = entry * 1.03
    return tp1, tp2, tp3


# -------------------------
# SYGNAŁ PRO v2
# -------------------------
def generuj_sygnal(scs, buy_zone, price, low_wide, high_wide,
                   t15, t60, t240, in_position):
    # SELL / odwrócenie
    if in_position and scs is not None:
        if t15 == "DOWN" and t60 != "UP" and scs <= 8:
            return "odwrócenie — rozważ sprzedaż", "red"

    # brak danych
    if price is None or low_wide is None or high_wide is None:
        return "czekaj", "gray"

    # BUY v2: t240 UP, t60 UP, t15 != DOWN + cena w widełkach
    if t240 == "UP" and t60 == "UP" and t15 != "DOWN":
        if low_wide <= price <= high_wide:
            return "BUY — cena w widełkach", "green"

    # watchlist: korekta w trendzie
    if t240 == "UP" and t60 == "UP" and t15 == "DOWN":
        return "watchlist — korekta w trendzie", "yellow"

    # konflikt / brak przewagi
    if t15 == "DOWN" and t60 == "UP" and t240 == "UP":
        return "sygnał niejednoznaczny — czekaj", "blue"

    return "czekaj", "gray"


# -------------------------
# BUDOWANIE WIERSZY TABELI
# -------------------------
def prepare_rows():
    history = load_history()
    rows = []

    for name, data in history.items():
        last_price = data.get("last_price")
        if last_price is not None:
            last_price = float(last_price)

        ohlc_15m = data.get("ohlc_15m") or {}
        ohlc_60m = data.get("ohlc_60m") or {}
        ohlc_240m = data.get("ohlc_240m") or {}

        t15 = trend_from_ohlc(ohlc_15m)
        t60 = trend_from_ohlc(ohlc_60m)
        t240 = trend_from_ohlc(ohlc_240m)

        scs = compute_scs_from_trends(t15, t60, t240)

        buy_zone, low_wide, high_wide = compute_buy_zone_and_widely(ohlc_15m)

        entry = data.get("entry")
        if entry is not None:
            entry = float(entry)
        in_position = entry is not None

        tp1, tp2, tp3 = compute_tps(entry)

        signal_text, signal_color = generuj_sygnal(
            scs=scs,
            buy_zone=buy_zone,
            price=last_price,
            low_wide=low_wide,
            high_wide=high_wide,
            t15=t15,
            t60=t60,
            t240=t240,
            in_position=in_position
        )

        rows.append({
            "name": name,
            "last_price": last_price,
            "scs": scs,

            "ohlc_15m": ohlc_15m,
            "ohlc_60m": ohlc_60m,
            "ohlc_240m": ohlc_240m,

            "trend15": t15,
            "trend60": t60,
            "trend240": t240,

            "trend15_icon": trend_icon(t15),
            "trend60_icon": trend_icon(t60),
            "trend240_icon": trend_icon(t240),

            "buy_zone": buy_zone,
            "low_wide": low_wide,
            "high_wide": high_wide,

            "entry": entry,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,

            "signal_text": signal_text,
            "signal_color": signal_color
        })

    # sortowanie: najpierw setup score (SCS), potem nazwa
    rows = sorted(
        rows,
        key=lambda x: (x["scs"] if x["scs"] is not None else -999, x["name"])
    )
    rows.reverse()  # najwyższy SCS na górze

    return rows


# -------------------------
# ROUTES
# -------------------------
@app.route("/")
def index():
    rows = prepare_rows()
    return render_template("index.html", rows=rows)


# JSON API — łatwe do integracji z botem / TV / JS
@app.route("/update_price", methods=["POST"])
def update_price():
    data = request.get_json(force=True)
    name = data.get("name")
    price = data.get("price")

    history = load_history()
    if name in history and price is not None:
        history[name]["last_price"] = float(price)
        save_history(history)

    return jsonify({"status": "ok"})


@app.route("/update_ohlc", methods=["POST"])
def update_ohlc():
    data = request.get_json(force=True)
    name = data.get("name")
    tf = data.get("tf")  # "15m", "60m", "240m"
    o = data.get("o")
    h = data.get("h")
    l = data.get("l")
    c = data.get("c")

    key = None
    if tf == "15m":
        key = "ohlc_15m"
    elif tf == "60m":
        key = "ohlc_60m"
    elif tf == "240m":
        key = "ohlc_240m"

    history = load_history()
    if name in history and key is not None:
        history[name][key] = {
            "o": float(o),
            "h": float(h),
            "l": float(l),
            "c": float(c)
        }
        save_history(history)

    return jsonify({"status": "ok"})


@app.route("/update_entry", methods=["POST"])
def update_entry():
    data = request.get_json(force=True)
    name = data.get("name")
    entry = data.get("entry")  # może być puste

    history = load_history()
    if name in history:
        if entry in ("", None):
            history[name]["entry"] = None
        else:
            history[name]["entry"] = float(entry)
        save_history(history)

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
