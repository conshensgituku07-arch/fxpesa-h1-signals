import os
import time
import requests
import yfinance as yf
import pandas as pd

# ============================================================
# FXPesa H1 Signal Assistant - Version 1
# Phone signal system
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Pairs to scan
PAIRS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "USDCHF": "CHF=X",
}

RISK_PERCENT = 0.5
RISK_REWARD = 4.0


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ CONFIRM", "callback_data": "confirm"},
                {"text": "❌ CANCEL", "callback_data": "cancel"}
            ]
        ]
    }

    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "reply_markup": keyboard
    }

    response = requests.post(url, json=data, timeout=20)

    if not response.ok:
        print("Telegram error:", response.text)


def get_data(symbol):
    data = yf.download(
        symbol,
        period="30d",
        interval="1h",
        auto_adjust=False,
        progress=False
    )

    if data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.dropna()

    return data


def calculate_indicators(data):

    data["EMA50"] = data["Close"].ewm(
        span=50,
        adjust=False
    ).mean()

    data["EMA200"] = data["Close"].ewm(
        span=200,
        adjust=False
    ).mean()

    data["EMA800"] = data["Close"].ewm(
        span=800,
        adjust=False
    ).mean()

    previous_close = data["Close"].shift(1)

    tr1 = data["High"] - data["Low"]
    tr2 = abs(data["High"] - previous_close)
    tr3 = abs(data["Low"] - previous_close)

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    data["ATR"] = true_range.rolling(14).mean()

    return data


def check_signal(pair, symbol):

    data = get_data(symbol)

    if data is None:
        return None

    data = calculate_indicators(data)

    if len(data) < 810:
        return None

    # Only use CLOSED candles
    previous = data.iloc[-2]
    pullback = data.iloc[-3]

    ema50 = previous["EMA50"]
    ema200 = previous["EMA200"]
    ema800 = previous["EMA800"]

    atr = previous["ATR"]

    close = previous["Close"]
    open_price = previous["Open"]

    # --------------------------------------------------------
    # BUY CONDITIONS
    # --------------------------------------------------------

    bullish_trend = (
        ema50 > ema200 and
        ema200 > ema800 and
        close > ema800
    )

    bullish_pullback = (
        pullback["Low"] <= pullback["EMA50"] or
        pullback["Low"] <= pullback["EMA200"]
    )

    bullish_confirmation = (
        close > open_price and
        close > pullback["High"] and
        close > ema50
    )

    if (
        bullish_trend and
        bullish_pullback and
        bullish_confirmation
    ):

        entry = float(close)

        stop = min(
            float(pullback["Low"]),
            entry - float(atr) * 1.5
        )

        risk = entry - stop

        if risk <= 0:
            return None

        target = entry + risk * RISK_REWARD

        return {
            "pair": pair,
            "direction": "BUY",
            "entry": entry,
            "stop": stop,
            "target": target,
            "risk": RISK_PERCENT
        }

    # --------------------------------------------------------
    # SELL CONDITIONS
    # --------------------------------------------------------

    bearish_trend = (
        ema50 < ema200 and
        ema200 < ema800 and
        close < ema800
    )

    bearish_pullback = (
        pullback["High"] >= pullback["EMA50"] or
        pullback["High"] >= pullback["EMA200"]
    )

    bearish_confirmation = (
        close < open_price and
        close < pullback["Low"] and
        close < ema50
    )

    if (
        bearish_trend and
        bearish_pullback and
        bearish_confirmation
    ):

        entry = float(close)

        stop = max(
            float(pullback["High"]),
            entry + float(atr) * 1.5
        )

        risk = stop - entry

        if risk <= 0:
            return None

        target = entry - risk * RISK_REWARD

        return {
            "pair": pair,
            "direction": "SELL",
            "entry": entry,
            "stop": stop,
            "target": target,
            "risk": RISK_PERCENT
        }

    return None


def format_signal(signal):

    direction = signal["direction"]

    emoji = "🟢" if direction == "BUY" else "🔴"

    return f"""
🚨 FXPESA H1 TRADE SIGNAL

Pair: {signal["pair"]}
Direction: {emoji} {direction}

Entry: {signal["entry"]:.5f}
Stop Loss: {signal["stop"]:.5f}
Take Profit: {signal["target"]:.5f}

Risk: {signal["risk"]}%
Risk/Reward: 1:{RISK_REWARD:.0f}

Strategy:
EMA 50 / 200 / 800
Pullback + confirmation
ATR filter

⚠️ Manual approval required.
Do NOT enter until you confirm.
"""


def main():

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram credentials are missing.")
        return

    print("Starting FXPesa H1 Signal Assistant...")

    for pair, symbol in PAIRS.items():

        try:

            signal = check_signal(pair, symbol)

            if signal:

                message = format_signal(signal)

                send_telegram(message)

                print("Signal sent:", pair, signal["direction"])

            else:

                print(pair, "- no valid setup")

        except Exception as error:

            print(pair, "- error:", error)


if __name__ == "__main__":
    main()
