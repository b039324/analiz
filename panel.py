# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="BIST Analiz", page_icon="📊", layout="centered")

st.markdown("""
<style>
    .block-container {padding-top: 2rem; max-width: 900px;}
    h1 {color: #00d4aa; font-size: 1.8rem;}
    .stTextInput input {font-size: 1.1rem;}
</style>
""", unsafe_allow_html=True)

st.title("📊 BIST Analiz Paneli")
st.caption("Hisse gir → veriyi kopyala → yapay zekaya yapıştır → yorum al.")

# ==================== GİRİŞ ====================
col1, col2 = st.columns([3, 1])
with col1:
    sembol_input = st.text_input("Hisse Sembolü", value="AKBNK", placeholder="Örn: AKBNK, KCHOL, THYAO")
with col2:
    periyot = st.selectbox("Periyot", ["1y", "2y", "5y"], index=1)

analiz_btn = st.button("🔍 Analiz Et", type="primary", use_container_width=True)

# ==================== YARDIMCI FONKSİYONLAR ====================
def fmt(v, suffix="", na="N/A"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return na
    try:
        return f"{v:.2f}{suffix}"
    except (ValueError, TypeError):
        return str(v)

def fmt_buyuk(v, na="N/A"):
    if v is None:
        return na
    try:
        return f"{v:,.0f}"
    except (ValueError, TypeError):
        return str(v)

def fmt_yuzde(v, na="N/A"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return na
    try:
        return f"{v*100:.2f}%"
    except (ValueError, TypeError):
        return str(v)

# ==================== ANALİZ ====================
if analiz_btn and sembol_input:
    sembol = sembol_input.strip().upper()
    if not sembol.endswith(".IS") and "." not in sembol:
        sembol = sembol + ".IS"

    with st.spinner(f"⏳ {sembol} verisi çekiliyor..."):
        try:
            hisse = yf.Ticker(sembol)
            df = hisse.history(period=periyot, interval="1d")
            df_h = hisse.history(period=periyot, interval="1wk")
            try:
                info = hisse.info
            except Exception:
                info = {}
        except Exception as e:
            st.error(f"❌ Veri çekme hatası: {e}")
            st.stop()

    if df.empty or len(df) < 60:
        st.error(f"❌ {sembol} için yeterli veri yok. Sembol doğru mu?")
        st.stop()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if isinstance(df_h.columns, pd.MultiIndex):
        df_h.columns = df_h.columns.get_level_values(0)

    # ==================== GÖSTERGELER ====================
    for span in [9, 21, 50, 100, 200]:
        df[f"EMA{span}"] = df["Close"].ewm(span=span, adjust=False).mean()
    for span in [20, 50, 200]:
        df[f"SMA{span}"] = df["Close"].rolling(span).mean()

    delta = df["Close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = -delta.where(delta < 0, 0).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + gain/loss))

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]      = ema12 - ema26
    df["MACD_Sig"]  = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Sig"]

    df["BB_Mid"]   = df["Close"].rolling(20).mean()
    df["BB_Std"]   = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["BB_Mid"] + 2 * df["BB_Std"]
    df["BB_Lower"] = df["BB_Mid"] - 2 * df["BB_Std"]
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"] * 100

    high_low   = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close  = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"]     = tr.rolling(14).mean()
    df["ATR_Pct"] = df["ATR"] / df["Close"] * 100

    low14  = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()
    df["Stoch_K"] = 100 * (df["Close"] - low14) / (high14 - low14)
    df["Stoch_D"] = df["Stoch_K"].rolling(3).mean()

    up_move   = df["High"].diff()
    down_move = -df["Low"].diff()
    plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    atr14     = tr.rolling(14).mean()
    plus_di   = 100 * pd.Series(plus_dm, index=df.index).rolling(14).mean() / atr14
    minus_di  = 100 * pd.Series(minus_dm, index=df.index).rolling(14).mean() / atr14
    dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df["ADX"] = dx.rolling(14).mean()

    df["OBV"]      = (np.sign(df["Close"].diff()) * df["Volume"]).fillna(0).cumsum()
    df["VWAP20"]   = (df["Close"] * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()
    df["Vol_MA20"] = df["Volume"].rolling(20).mean()

    son    = df.iloc[-1]
    onceki = df.iloc[-2]

    # ==================== TARİH ====================
    tarih_str = df.index[-1].strftime("%d.%m.%Y")

    # ==================== XU100 ve USDTRY ====================
    try:
        xu100 = yf.Ticker("XU100.IS").history(period="5d", interval="1d")
        xu100_degisim = (xu100["Close"].iloc[-1] / xu100["Close"].iloc[-2] - 1) * 100
        xu100_deger = xu100["Close"].iloc[-1]
    except Exception:
        xu100_deger, xu100_degisim = None, None

    try:
        usdtry = yf.Ticker("USDTRY=X").history(period="5d", interval="1d")
        usdtry_deger = usdtry["Close"].iloc[-1]
    except Exception:
        usdtry_deger = None

    # ==================== METİN ÇIKTISI ====================
    L = []
    L.append("=" * 50)
    L.append(f"  {sembol} - TEKNİK + TEMEL VERİ")
    L.append(f"  Tarih: {tarih_str}")
    L.append("=" * 50)

    L.append(f"\nFİYAT ({tarih_str})")
    L.append(f"  Kapanış      : {son['Close']:.2f} TL")
    L.append(f"  Açılış       : {son['Open']:.2f} TL")
    L.append(f"  Yüksek       : {son['High']:.2f} TL")
    L.append(f"  Düşük        : {son['Low']:.2f} TL")
    L.append(f"  Değişim      : {((son['Close']-onceki['Close'])/onceki['Close']*100):+.2f}%")

    L.append(f"\nEMA / SMA DEĞERLERİ ({tarih_str})")
    for span in [9, 21, 50, 100, 200]:
        L.append(f"  EMA {span:<4}     : {son[f'EMA{span}']:.2f} TL")
    for span in [20, 50, 200]:
        L.append(f"  SMA {span:<4}     : {son[f'SMA{span}']:.2f} TL")

    L.append(f"\nFİYATIN EMA'LARA UZAKLIĞI ({tarih_str})")
    for span in [21, 50, 100, 200]:
        L.append(f"  EMA {span:<4}     : {((son['Close']/son[f'EMA{span}']-1)*100):+.2f}%")

    L.append(f"\nMOMENTUM ({tarih_str})")
    L.append(f"  RSI (14)     : {son['RSI']:.2f}")
    L.append(f"  MACD         : {son['MACD']:.3f}")
    L.append(f"  MACD Sinyal  : {son['MACD_Sig']:.3f}")
    L.append(f"  MACD Hist    : {son['MACD_Hist']:.3f}")
    L.append(f"  Stoch %K     : {son['Stoch_K']:.2f}")
    L.append(f"  Stoch %D     : {son['Stoch_D']:.2f}")

    L.append(f"\nTREND GÜCÜ ({tarih_str})")
    L.append(f"  ADX (14)     : {son['ADX']:.2f}")
    L.append(f"  +DI          : {plus_di.iloc[-1]:.2f}")
    L.append(f"  -DI          : {minus_di.iloc[-1]:.2f}")

    L.append(f"\nVOLATİLİTE ({tarih_str})")
    L.append(f"  ATR (14)     : {son['ATR']:.2f} TL")
    L.append(f"  ATR %        : {son['ATR_Pct']:.2f}%")
    L.append(f"  BB Üst       : {son['BB_Upper']:.2f} TL")
    L.append(f"  BB Orta      : {son['BB_Mid']:.2f} TL")
    L.append(f"  BB Alt       : {son['BB_Lower']:.2f} TL")
    L.append(f"  BB Genişlik  : {son['BB_Width']:.2f}%")

    L.append(f"\nHACİM ({tarih_str})")
    L.append(f"  Bugünkü      : {int(son['Volume']):,}")
    L.append(f"  20g Ortalama : {int(son['Vol_MA20']):,}")
    L.append(f"  Oran         : {(son['Volume']/son['Vol_MA20']):.2f}x")
    L.append(f"  VWAP (20g)   : {son['VWAP20']:.2f} TL")
    L.append(f"  OBV (bugün)  : {int(son['OBV']):,}")

    L.append(f"\nTEMEL VERİLER ({tarih_str})")
    L.append(f"  Şirket       : {info.get('longName', 'N/A')}")
    L.append(f"  Sektör       : {info.get('sector', 'N/A')}")
    L.append(f"  Endüstri     : {info.get('industry', 'N/A')}")
    L.append(f"  Piyasa Değ.  : {fmt_buyuk(info.get('marketCap'))} TL")
    L.append(f"  F/K (TTM)    : {fmt(info.get('trailingPE'))}")
    L.append(f"  İleri F/K    : {fmt(info.get('forwardPE'))}")
    L.append(f"  PD/DD        : {fmt(info.get('priceToBook'))}")
    L.append(f"  FD/FAVÖK     : {fmt(info.get('enterpriseToEbitda'))}")
    L.append(f"  Kâr Marjı    : {fmt_yuzde(info.get('profitMargins'))}")
    L.append(f"  Faaliyet Marjı: {fmt_yuzde(info.get('operatingMargins'))}")
    L.append(f"  ROE          : {fmt_yuzde(info.get('returnOnEquity'))}")
    L.append(f"  ROA          : {fmt_yuzde(info.get('returnOnAssets'))}")
    L.append(f"  Gelir Büyüme : {fmt_yuzde(info.get('revenueGrowth'))}")
    L.append(f"  Kâr Büyüme   : {fmt_yuzde(info.get('earningsGrowth'))}")
    L.append(f"  EPS (TTM)    : {fmt(info.get('trailingEps'))}")
    L.append(f"  İleri EPS    : {fmt(info.get('forwardEps'))}")
    L.append(f"  Borç/Özkaynak: {fmt(info.get('debtToEquity'))}")
    L.append(f"  Cari Oran    : {fmt(info.get('currentRatio'))}")
    L.append(f"  Temettü Ver. : {fmt_yuzde(info.get('dividendYield'))}")
    L.append(f"  Dağıtım Oranı: {fmt_yuzde(info.get('payoutRatio'))}")

    L.append(f"\nSON 10 GÜN (OHLC + Hacim)")
    L.append(f"  {'Tarih':<12}{'Açılış':>9}{'Yüksek':>9}{'Düşük':>9}{'Kapanış':>9}{'Hacim':>14}")
    for i in range(-10, 0):
        r = df.iloc[i]
        L.append(f"  {df.index[i].strftime('%d.%m.%Y'):<12}"
                 f"{r['Open']:>9.2f}{r['High']:>9.2f}{r['Low']:>9.2f}"
                 f"{r['Close']:>9.2f}{int(r['Volume']):>14,}")

    L.append(f"\nSON 20 GÜN / 52 HAFTALIK ({tarih_str})")
    L.append(f"  20g Yüksek   : {df['High'].tail(20).max():.2f} TL")
    L.append(f"  20g Düşük    : {df['Low'].tail(20).min():.2f} TL")
    L.append(f"  52h Yüksek   : {df['High'].tail(252).max():.2f} TL")
    L.append(f"  52h Düşük    : {df['Low'].tail(252).min():.2f} TL")
    y52 = df['High'].tail(252).max()
    d52 = df['Low'].tail(252).min()
    L.append(f"  52h Konum    : {((son['Close']-d52)/(y52-d52)*100):.1f}%")

    L.append(f"\nHAFTALIK GÖRÜNÜM ({tarih_str})")
    if len(df_h) >= 21:
        son_h = df_h.iloc[-1]
        ema21_h = df_h["Close"].ewm(span=21, adjust=False).mean().iloc[-1]
        ema50_h = df_h["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
        L.append(f"  Haftalık Kapanış: {son_h['Close']:.2f} TL")
        L.append(f"  EMA 21 (H)      : {ema21_h:.2f} TL")
        L.append(f"  EMA 50 (H)      : {ema50_h:.2f} TL")

    L.append(f"\nKARŞILAŞTIRMA ({tarih_str})")
    if xu100_deger:
        L.append(f"  XU100        : {xu100_deger:.2f} ({xu100_degisim:+.2f}%)")
    if usdtry_deger:
        L.append(f"  USD/TRY      : {usdtry_deger:.4f}")

    L.append("\n" + "=" * 50)

    metin = "\n".join(L)

    # ==================== GÖSTER ====================
    st.success(f"✅ {sembol} analizi hazır! ({tarih_str})")
    st.info("👇 Sağ üstteki **kopyala ikonuna** tıkla, sonra yapay zekaya yapıştır.")

    st.code(metin, language=None)

else:
    if analiz_btn:
        st.warning("⚠️ Lütfen bir hisse sembolü gir.")
