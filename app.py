import json
from flask import Flask, request, jsonify, render_template
from datetime import datetime
import os

app = Flask(__name__)

DATA_FILE = "history.json"

# ---------------------------------------------------------
# Helper: load/save JSON
# ---------------------------------------------------------

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ---------------------------------------------------------
# Instruments
# ---------------------------------------------------------

INSTRUMENTS = [
    "Alior Bank (ALR)",
    "Allegro.eu (ALE)",
    "Asseco Poland (ACP)",
    "Budimex (BDX)",
    "CD Projekt (CDR)",
    "Dino Polska (DNP)",
    "KGHM Polska Miedź (KGH)",
    "Kruk (KRU)",
    "LPP (LPP)",
    "mBank (MBK)",
    "Modivo (CCC)",
    "Pekao (PEO)",
    "Pepco Group (PCO)",
    "PKN Orlen (PKN)",
    "PKO Bank Polski (PKO)",
    "PZU (PZU)",
    "BNP Paribas Bank Polska (BNP)",
    "Bank Handlowy (BHW)",
    "Beta ETF WIG20TR (BETAMWIG20TR)",
    "Beta ETF mWIG40TR (BETAMWIG40TR)"
]

# ---------------------------------------------------------
# SCS 4.97 PRO — profil B3 (agresywny)
# ---------------------------------------------------------

def sma(values, length):
    if len(values) < length:
        return None
    return sum(values[-length:]) / length

def calculate_scs(history):
    prices = [h["price"] for h in history]
    if len(prices) < 2:
        return 0

    last = prices[-1]
    prev = prices[-2]

    scs = 0

    sma5 = sma(prices, 5)
    sma10 = sma(prices, 10)

    # 1) trend krótki — agresywny
    if sma5 is not None and last > sma5 * 0.998:
        scs += 4

    # 2) trend średni — agresywny
    if sma10 is not None and last > sma10 * 0.999:
        scs += 4

    # 3) momentum — agresywne
    if last >= prev:
        scs += 4

    # 4) siła — agresywna
    if sma10 is not None and last > sma10 * 1.005:
        scs += 4

    # 5) stabilność — agresywna
    change = abs(last - prev) / prev
    if change < 0.03:
        scs += 4

    return scs

# ---------------------------------------------------------
# Swing detector C2 + odbicie 0.2% + DEBUG
# ---------------------------------------------------------

def detect_correction_debug(history):
    debug = {
        "has_low": False,
        "low": None,
        "close_threshold": None,
        "bounce": False,
        "bz_low": None,
        "bz_high": None,
        "reason": ""
    }

    if len(history) < 5:
        debug["reason"] = "not enough data (min 5 prices)"
        return None, debug

    prices = [h["price"] for h in history]

    low_idx = None
    for i in range(len(prices) - 3, 1, -1):
        if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
            low_idx = i
            break

    if low_idx is None:
        debug["reason"] = "no swing low detected"
        return None, debug

    low_price = prices[low_idx]
    debug["has_low"] = True
    debug["low"] = low_price

    close_threshold = low_price * 1.002  # 0.2%
    debug["close_threshold"] = close_threshold

    close_price = None
    for j in range(low_idx + 1, len(prices)):
        if prices[j] >= close_threshold:
            close_price = prices[j]
            break

    if close_price is None:
        debug["reason"] = "no bounce above CLOSE threshold"
        return None, debug

    debug["bounce"] = True
    debug["bz_low"] = low_price
    debug["bz_high"] = close_price
    debug["reason"] = "correction and bounce detected"

    correction = {
        "low": low_price,
        "close": close_price,
        "bz_low": low_price,
        "bz_high": close_price
    }
    return correction, debug

# ---------------------------------------------------------
# Init structure
# ---------------------------------------------------------

def ensure_instrument(data, instrument):
    if instrument not in data:
        data[instrument] = {
            "history": [],
            "entry": None,
            "tp1": None,
            "tp2": None,
            "tp3": None,
            "buy_zone": None,
            "signal": "WAIT",
            "scs": 0,
            "debug": {}
        }

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/update_price", methods=["POST"])
def update_price():
    data = load_data()
    payload = request.json

    instrument = payload["instrument"]
    price = float(payload["price"])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ensure_instrument(data, instrument)

    data[instrument]["history"].append({
        "price": price,
        "time": timestamp
    })

    # SCS B3
    scs = calculate_scs(data[instrument]["history"])
    data[instrument]["scs"] = scs

    # Swing + BUY ZONE + DEBUG
    correction, dbg = detect_correction_debug(data[instrument]["history"])
    signal = "WAIT"
    signal_reason = ""

    entry = data[instrument]["entry"]

    if correction:
        data[instrument]["buy_zone"] = {
            "low": correction["bz_low"],
            "high": correction["bz_high"]
        }

        bz_low = correction["bz_low"]
        bz_high = correction["bz_high"]

        # SELL logiczny
        if entry is not None and scs <= 8:
            signal = "SELL"
            signal_reason = "SELL: SCS <= 8 with active entry"

        # BUY logiczny
        elif scs >= 12 and bz_low <= price <= bz_high:
            signal = "BUY"
            signal_reason = "BUY: SCS >= 12 and price in BUY ZONE"

        else:
            signal = "WAIT"
            if scs < 12:
                signal_reason = "WAIT: SCS < 12"
            elif price < bz_low:
                signal_reason = "WAIT: price below BUY ZONE"
            elif price > bz_high:
                signal_reason = "WAIT: price above BUY ZONE"
            else:
                signal_reason = "WAIT: conditions not met"

    else:
        data[instrument]["buy_zone"] = None
        signal = "WAIT"
        signal_reason = "WAIT: " + (dbg["reason"] or "no correction")

    data[instrument]["signal"] = signal

    dbg["signal_reason"] = signal_reason
    dbg["scs"] = scs
    dbg["last_price"] = price
    data[instrument]["debug"] = dbg

    save_data(data)
    return jsonify({"status": "ok"})

@app.route("/set_entry", methods=["POST"])
def set_entry():
    data = load_data()
    payload = request.json

    instrument = payload["instrument"]
    entry_value = payload["entry"]

    ensure_instrument(data, instrument)

    # CZYSZCZENIE ENTRY — NOWOŚĆ W 4.97.5
    if entry_value in ["", None] or float(entry_value) <= 0:
        data[instrument]["entry"] = None
        data[instrument]["tp1"] = None
        data[instrument]["tp2"] = None
        data[instrument]["tp3"] = None
        data[instrument]["signal"] = "WAIT"
        save_data(data)
        return jsonify({"status": "entry_cleared"})

    # NORMALNE USTAWIENIE ENTRY
    entry = float(entry_value)
    data[instrument]["entry"] = entry
    data[instrument]["tp1"] = round(entry * 1.01, 2)
    data[instrument]["tp2"] = round(entry * 1.02, 2)
    data[instrument]["tp3"] = round(entry * 1.03, 2)

    save_data(data)
    return jsonify({"status": "ok"})

@app.route("/get_data", methods=["GET"])
def get_data():
    data = load_data()
    for inst in INSTRUMENTS:
        ensure_instrument(data, inst)
    save_data(data)
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
