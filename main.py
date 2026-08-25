import os
import time
import requests
import yfinance as yf
import pandas as pd

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

PAIRS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "USDCHF": "CHF=X"
}

RISK_REWARD = 4.0


def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram credentials are missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, data=data, timeout=20)
        print(response.text)
    except Exception as e:
        print("Telegram error:", e)


def get_data(symbol):
    try:
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

    except Exception as e:
        print(symbol, e)
        return None


def calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def analyze(pair, symbol):
    data = get_data(symbol)

    if data is None or len(data) < 210:
        return None

    close = data["Close"]

    data["EMA50"] = close.ewm(span=50, adjust=False).mean()
    data["EMA200"] = close.ewm(span=200, adjust=False).mean()
    data["EMA800"] = close.ewm(span=800, adjust=False).mean()

    data["RSI"] = calculate_rsi(close)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    data["MACD"] = ema12 - ema26
    data["MACD_SIGNAL"] = data["MACD"].ewm(
        span=9,
        adjust=False
    ).mean()

    last = data.iloc[-1]

    price = float(last["Close"])
    ema50 = float(last["EMA50"])
    ema200 = float(last["EMA200"])
    ema800 = float(last["EMA800"])
    rsi = float(last["RSI"])
    macd = float(last["MACD"])
    macd_signal = float(last["MACD_SIGNAL"])

    # BULLISH SETUP
    bullish = (
        price > ema50
        and ema50 > ema200
        and ema200 > ema800
        and rsi >= 50
        and rsi <= 68
        and macd > macd_signal
    )

    # BEARISH SETUP
    bearish = (
        price < ema50
        and ema50 < ema200
        and ema200 < ema800
        and rsi <= 50
        and rsi >= 32
        and macd < macd_signal
    )

    if not bullish and not bearish:
        return None

    # Simple volatility estimate
    recent_range = (
        data["High"].tail(14) - data["Low"].tail(14)
    ).mean()

    risk = float(recent_range)

    if risk <= 0:
        return None

    if bullish:
        direction = "BUY"
        stop_loss = price - risk
        take_profit = price + (risk * RISK_REWARD)

    else:
        direction = "SELL"
        stop_loss = price + risk
        take_profit = price - (risk * RISK_REWARD)

    return {
        "pair": pair,
        "direction": direction,
        "price": price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rsi": rsi,
        "ema50": ema50,
        "ema200": ema200,
        "ema800": ema800,
        "macd": macd,
        "macd_signal": macd_signal
    }


def format_signal(signal):

    return f"""
🚨 FXPesa H1 SIGNAL

Pair: {signal['pair']}
Direction: {signal['direction']}

Entry: {signal['price']:.5f}
Stop Loss: {signal['stop_loss']:.5f}
Take Profit: {signal['take_profit']:.5f}

Risk/Reward: 1:4

RSI: {signal['rsi']:.1f}

EMA 50: {signal['ema50']:.5f}
EMA 200: {signal['ema200']:.5f}
EMA 800: {signal['ema800']:.5f}

MACD: {signal['macd']:.5f}
Signal: {signal['macd_signal']:.5f}

⚠️ SIGNAL ONLY
Confirm the setup on MT5 before entering.

This bot does NOT place the trade automatically.
"""


def main():

    print("FXPesa H1 Signal Assistant started.")

    signals_found = 0

    for pair, symbol in PAIRS.items():

        print("Scanning", pair)

        signal = analyze(pair, symbol)

        if signal:

            message = format_signal(signal)

            send_telegram(message)

            signals_found += 1

            print("Signal found:", pair)

        else:
            print("No valid setup:", pair)

    print("Scan complete.")
    print("Signals found:", signals_found)


if __name__ == "__main__":
    main()
