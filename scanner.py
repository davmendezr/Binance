import streamlit as st
import requests
import re
import pandas as pd
import numpy as np
import ta
from datetime import datetime

# BINANCE_FUTURES_BASE = "https://binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"

INTERVAL = "4h" 
FEATURES = ["rsi", "mfi", "stoch_k", "stoch_d", "macd_hist", "hist_relativo", "vol_ratio", "atr"]

COINMARKETCAP_API_KEY = "7a203fe401be4ca5840dd11c1215254c"
CMC_BASE_URL = "https://coinmarketcap.com"

def get_all_usdt_futures_symbols():
    response = requests.get(f"{BINANCE_FUTURES_BASE}/fapi/v1/exchangeInfo", timeout=10)
    response.raise_for_status()
    data = response.json()
    symbols = [
        s["symbol"] for s in data["symbols"]
        if s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
    ]
    cjk_pattern = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]')
    return [s for s in symbols if not cjk_pattern.search(s)]

def get_ohlc(symbol: str, interval: str = "1h", limit: int = 500):
    url = f"{BINANCE_FUTURES_BASE}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data or len(data) < 50: return None
        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume", 
            "close_time", "quote_asset_volume", "num_trades", 
            "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        return df[["time", "open", "high", "low", "close", "volume"]].dropna()
    except Exception:
        return None

def calculate_relative_macd(df):
    ema_fast = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['close'].ewm(span=26, adjust=False).mean()
    macd_relativo = ((ema_fast - ema_slow) / ema_slow) * 100
    signal_relativa = macd_relativo.ewm(span=9, adjust=False).mean()
    return macd_relativo - signal_relativa

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)
    df["mfi"] = ta.volume.money_flow_index(df["high"], df["low"], df["close"], df["volume"], window=14)
    stoch = ta.momentum.StochRSIIndicator(df["close"], window=14)
    df["stoch_k"] = stoch.stochrsi_k()
    df["stoch_d"] = stoch.stochrsi_d()
    df["macd_hist"] = ta.trend.MACD(df["close"]).macd_diff()
    df["hist_relativo"] = calculate_relative_macd(df)
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)
    return df.dropna().reset_index(drop=True)

# --- INTERFAZ GRÁFICA DE STREAMLIT ---
st.title("📈 Escáner de Reversiones Futuros Binance")
st.write("Ejecución esporádica bajo demanda 100% gratuita.")

if st.button("🚀 Iniciar Escaneo de Mercado", variant="primary"):
    with st.spinner("Procesando criptomonedas en tiempo real..."):
        try:
            all_symbols = get_all_usdt_futures_symbols()
            rows = []

            for sym in all_symbols:
                df = get_ohlc(sym, interval=INTERVAL, limit=100)
                if df is not None:
                    df = add_indicators(df)
                    if not df.empty:
                        row = df.iloc[-1]
                        rows.append({"Timestamp": datetime.now(), "Symbol": sym, **{f: row[f] for f in FEATURES}})

            if rows:
                df_out = pd.DataFrame(rows)
                df_out["KPI_avg2"] = (df_out["rsi"] + df_out["mfi"]) / 2
                
                st.success("¡Análisis completado con éxito!")
                # Desplegar la tabla interactiva directamente en la pantalla web
                st.dataframe(df_out[['Symbol', 'rsi', 'mfi', 'KPI_avg2']])
            else:
                st.warning("❌ No se encontraron patrones de reversión en este momento.")
        except Exception as e:
            st.error(f"Error de ejecución: {str(e)}")
