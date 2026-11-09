# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta

# Türkiye kalıcı olarak UTC+3 (yaz saati yok); sunucu saati ne olursa olsun İstanbul saati yazılır
TR_TZ = timezone(timedelta(hours=3))

def cekim_zamani():
    """Verinin çekildiği an: 'GG.AA.YYYY SS:DD:SS (İstanbul)'"""
    return datetime.now(TR_TZ).strftime("%d.%m.%Y %H:%M:%S") + " (İstanbul)"

st.set_page_config(page_title="BIST & Coin Analiz", page_icon="📊", layout="centered")

st.markdown("""
<style>
    .block-container {padding-top: 2rem; max-width: 900px;}
    h1 {color: #00d4aa; font-size: 1.8rem;}
    .stTextInput input {font-size: 1.1rem;}
</style>
""", unsafe_allow_html=True)

st.title("📊 BIST & Coin Analiz Paneli")
st.caption("Hisse (AKBNK) veya Coin (BTC, ETH, SOL) gir → veriyi kopyala → yapay zekaya yapıştır → yorum al.")

# Endeks listeleri: Borsa İstanbul 1 Ekim - 31 Aralık 2026 dönemi (her çeyrek güncellenir)
# ==================== BIST 30 LİSTESİ ====================
BIST30 = [
    "AKBNK", "AEFES", "ASELS", "ASTOR", "BIMAS",
    "TRMET", "EKGYO", "ENKAI", "EREGL", "FROTO",
    "GUBRF", "SAHOL", "KRDMD", "KCHOL", "MGROS",
    "PGSUS", "PETKM", "SASA", "TAVHL", "TOASO",
    "TCELL", "TUPRS", "TRALT", "THYAO", "GARAN",
    "ISCTR", "SISE", "VAKBN", "TTKOM", "YKBNK"
]

# ==================== BIST 100 LİSTESİ ====================
BIST100 = [
    "AGHOL", "AHGAZ", "AKBNK", "AKCNS", "AKFYE", "AKSA", "AKSEN", "ALARK",
    "ALBRK", "ALTNY", "ANHYT", "ANSGR", "AEFES", "ARCLK", "ASELS", "ASTOR",
    "AYGAZ", "BTCIM", "BERA", "BIMAS", "BINHO", "BRSAN", "BRYAT", "CCOLA",
    "CVKMD", "CWENE", "CANTE", "CIMSA", "DOHOL", "DOAS", "ECILC", "ECZYT",
    "EGEEN", "EGGUB", "EKGYO", "ENJSA", "ENERY", "ENKAI", "ENTRA", "EREGL",
    "EUREN", "FENER", "FROTO", "GLYHO", "GUBRF", "GLRMK", "GRSEL", "GWIND",
    "SAHOL", "HEKTS", "ISDMR", "ISMEN", "KARSN", "KATMR", "KCAER", "KRDMD",
    "KCHOL", "KORDS", "LMKDC", "MAVI", "MGROS", "MPARK", "OBAMS", "ODAS",
    "OTKAR", "OYAKC", "PAHOL", "PGSUS", "PETKM", "RGYAS", "RYSAS", "SASA",
    "SNGYO", "SOKM", "TABGD", "TAVHL", "TCKRC", "TKFEN", "TOASO", "TRGYO",
    "TRMET", "TRENJ", "TTRAK", "TUKAS", "TCELL", "TUPRS", "TRALT", "THYAO",
    "GARAN", "HALKB", "ISCTR", "TSKB", "TURSG", "SISE", "VAKBN", "TTKOM",
    "ULKER", "VESTL", "YKBNK", "ZOREN"
]

# ==================== COIN LİSTESİ ====================
COIN_LISTESI = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT",
    "MATIC", "LINK", "LTC", "BCH", "ATOM", "ETC", "XLM", "ALGO",
    "VET", "FIL", "TRX", "EOS", "AAVE", "UNI", "MKR", "COMP",
    "SUSHI", "CRV", "SNX", "YFI", "GRT", "MANA", "SAND", "AXS"
]

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

def donem_getirisi(veri, gun):
    try:
        seri = veri["Close"].dropna()
        return (seri.iloc[-1] / seri.iloc[-(gun + 1)] - 1) * 100 if len(seri) > gun else None
    except Exception:
        return None


def hacim_profili(veri, gun=60, kademe=12):
    try:
        parca = veri.tail(gun).dropna(subset=["High", "Low", "Close", "Volume"])
        if len(parca) < 10 or parca["Volume"].sum() <= 0:
            return None
        tipik = (parca["High"] + parca["Low"] + parca["Close"]) / 3
        alt, ust = float(tipik.min()), float(tipik.max())
        if not np.isfinite(alt) or not np.isfinite(ust) or ust <= alt:
            return None
        sinir = np.linspace(alt, ust, kademe + 1)
        kutu = pd.cut(tipik, bins=sinir, include_lowest=True, labels=False)
        hacim = parca.groupby(kutu, observed=False)["Volume"].sum().reindex(
            range(kademe), fill_value=0).astype(float)
        poc = int(hacim.values.argmax())
        sol = sag = poc
        toplam = float(hacim.iloc[poc])
        hedef = float(hacim.sum()) * 0.70
        while toplam < hedef and (sol > 0 or sag < kademe - 1):
            lh = float(hacim.iloc[sol - 1]) if sol > 0 else -1
            rh = float(hacim.iloc[sag + 1]) if sag < kademe - 1 else -1
            if rh >= lh and sag < kademe - 1:
                sag += 1
                toplam += float(hacim.iloc[sag])
            elif sol > 0:
                sol -= 1
                toplam += float(hacim.iloc[sol])
            else:
                break
        merkez = (sinir[:-1] + sinir[1:]) / 2
        return {"poc": float(merkez[poc]), "val": float(sinir[sol]), "vah": float(sinir[sag + 1])}
    except Exception:
        return None


# ==================== MARKDOWN ÇIKTISI ====================
def md_indir_butonu(baslik, metin, dosya_adi, anahtar):
    """Analiz metnini .md dosyası olarak indirten buton gösterir."""
    md = (
        f"# {baslik}\n\n"
        f"_Veri çekim zamanı: {cekim_zamani()}_\n\n"
        "```text\n" + metin + "\n```\n"
    )
    zaman_damgasi = datetime.now(TR_TZ).strftime("%Y%m%d_%H%M")
    ayarlar = dict(
        label="⬇️ Markdown (.md) olarak indir",
        data=md.encode("utf-8"),
        file_name=f"{dosya_adi}_{zaman_damgasi}.md",
        mime="text/markdown",
        use_container_width=True,
        key=anahtar,
    )
    try:
        # Yeni Streamlit: indirirken sayfa yeniden çalışmaz, sonuç ekranda kalır
        st.download_button(on_click="ignore", **ayarlar)
    except TypeError:
        st.download_button(**ayarlar)

# ==================== HİSSE / COİN ANALİZİ ====================
def analiz_et(sembol_ham, periyot="2y"):
    """Hisse veya coin için tam analiz metni döndürür. Hata olursa None döner."""
    try:
        sembol = sembol_ham.strip().upper()

        # Coin mi hisse mi?
        if sembol in COIN_LISTESI or sembol.endswith("-USD"):
            if not sembol.endswith("-USD"):
                sembol = sembol + "-USD"
            coin_mi = True
        else:
            if not sembol.endswith(".IS") and "." not in sembol:
                sembol = sembol + ".IS"
            coin_mi = False

        hisse = yf.Ticker(sembol)
        df = hisse.history(period=periyot, interval="1d")
        df_h = hisse.history(period=periyot, interval="1wk")
        df_m = hisse.history(period=periyot, interval="1mo")
        try:
            info = hisse.info
        except Exception:
            info = {}

        if df.empty or len(df) < 60:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if isinstance(df_h.columns, pd.MultiIndex):
            df_h.columns = df_h.columns.get_level_values(0)
        if isinstance(df_m.columns, pd.MultiIndex):
            df_m.columns = df_m.columns.get_level_values(0)

        # Göstergeler
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
        tarih_str = df.index[-1].strftime("%d.%m.%Y")

        # XU100 ve USDTRY (sadece hisseler için)
        xu100_deger, xu100_degisim = None, None
        usdtry_deger = None
        xu100_gecmis, xbank_gecmis = None, None

        if not coin_mi:
            try:
                xu100 = yf.Ticker("XU100.IS").history(period="5d", interval="1d")
                xu100_degisim = (xu100["Close"].iloc[-1] / xu100["Close"].iloc[-2] - 1) * 100
                xu100_deger = xu100["Close"].iloc[-1]
                xu100_gecmis = yf.Ticker("XU100.IS").history(period=periyot, interval="1d")
            except Exception:
                pass

            try:
                usdtry = yf.Ticker("USDTRY=X").history(period="5d", interval="1d")
                usdtry_deger = usdtry["Close"].iloc[-1]
            except Exception:
                pass

            try:
                xbank_gecmis = yf.Ticker("XBANK.IS").history(period=periyot, interval="1d")
            except Exception:
                pass

        L = []
        L.append("=" * 50)
        if coin_mi:
            L.append(f"  {sembol} - TEKNİK VERİ (COIN)")
        else:
            L.append(f"  {sembol} - TEKNİK + TEMEL VERİ")
        L.append(f"  Tarih: {tarih_str}")
        L.append("=" * 50)

        L.append(f"\nFİYAT ({tarih_str})")
        L.append(f"  Kapanış      : {son['Close']:.2f}")
        L.append(f"  Açılış       : {son['Open']:.2f}")
        L.append(f"  Yüksek       : {son['High']:.2f}")
        L.append(f"  Düşük        : {son['Low']:.2f}")
        L.append(f"  Değişim      : {((son['Close']-onceki['Close'])/onceki['Close']*100):+.2f}%")

        L.append(f"\nEMA / SMA DEĞERLERİ ({tarih_str})")
        for span in [9, 21, 50, 100, 200]:
            L.append(f"  EMA {span:<4}     : {son[f'EMA{span}']:.2f}")
        for span in [20, 50, 200]:
            L.append(f"  SMA {span:<4}     : {son[f'SMA{span}']:.2f}")

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
        L.append(f"  ATR (14)     : {son['ATR']:.2f}")
        L.append(f"  ATR %        : {son['ATR_Pct']:.2f}%")
        L.append(f"  BB Üst       : {son['BB_Upper']:.2f}")
        L.append(f"  BB Orta      : {son['BB_Mid']:.2f}")
        L.append(f"  BB Alt       : {son['BB_Lower']:.2f}")
        L.append(f"  BB Genişlik  : {son['BB_Width']:.2f}%")

        L.append(f"\nHACİM ({tarih_str})")
        L.append(f"  Bugünkü      : {int(son['Volume']):,}")
        L.append(f"  20g Ortalama : {int(son['Vol_MA20']):,}")
        L.append(f"  Oran         : {(son['Volume']/son['Vol_MA20']):.2f}x")
        L.append(f"  VWAP (20g)   : {son['VWAP20']:.2f}")
        L.append(f"  OBV (bugün)  : {int(son['OBV']):,}")

        L.append(f"\nTEMEL VERİLER ({tarih_str})")
        if coin_mi:
            L.append(f"  Coin         : {sembol}")
            L.append(f"  Not          : Coinlerde temel veri (F/K, PD/DD) bulunmaz.")
        else:
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
        L.append(f"  20g Yüksek   : {df['High'].tail(20).max():.2f}")
        L.append(f"  20g Düşük    : {df['Low'].tail(20).min():.2f}")
        L.append(f"  52h Yüksek   : {df['High'].tail(252).max():.2f}")
        L.append(f"  52h Düşük    : {df['Low'].tail(252).min():.2f}")
        y52 = df['High'].tail(252).max()
        d52 = df['Low'].tail(252).min()
        L.append(f"  52h Konum    : {((son['Close']-d52)/(y52-d52)*100):.1f}%")

        L.append(f"\nHAFTALIK GÖRÜNÜM ({tarih_str})")
        if len(df_h) >= 21:
            son_h = df_h.iloc[-1]
            ema21_h = df_h["Close"].ewm(span=21, adjust=False).mean().iloc[-1]
            ema50_h = df_h["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
            L.append(f"  Haftalık Kapanış: {son_h['Close']:.2f}")
            L.append(f"  EMA 21 (H)      : {ema21_h:.2f}")
            L.append(f"  EMA 50 (H)      : {ema50_h:.2f}")

        L.append(f"\\nAYLIK GÖRÜNÜM ({tarih_str})")
        if len(df_m) >= 3:
            son_m = df_m.iloc[-1]
            ema6_m = df_m["Close"].ewm(span=6, adjust=False).mean().iloc[-1]
            ema12_m = df_m["Close"].ewm(span=12, adjust=False).mean().iloc[-1]
            L.append(f"  Aylık Kapanış   : {son_m['Close']:.2f}")
            L.append(f"  EMA 6 (A)       : {ema6_m:.2f}")
            L.append(f"  EMA 12 (A)      : {ema12_m:.2f}")
        else:
            L.append("  Aylık veri      : Yetersiz")

        L.append(f"\\nDESTEK / DİRENÇ REFERANSLARI ({tarih_str})")
        for gun in [20, 60]:
            parca = df.tail(gun)
            if len(parca) >= min(gun, 10):
                L.append(f"  Son {gun}g Dip    : {parca['Low'].min():.2f}")
                L.append(f"  Son {gun}g Tepe   : {parca['High'].max():.2f}")

        profil = hacim_profili(df, gun=60, kademe=12)
        L.append(f"\\nHACİM PROFİLİ (SON 60 GÜN) ({tarih_str})")
        if profil:
            L.append(f"  POC (En yoğun)   : {profil['poc']:.2f}")
            L.append(f"  Değer Alanı Alt  : {profil['val']:.2f}")
            L.append(f"  Değer Alanı Üst  : {profil['vah']:.2f}")
            L.append("  Not              : Yaklaşık tipik fiyat-hacim dağılımıdır.")
        else:
            L.append("  Hacim profili    : Hesaplanamadı")

        if not coin_mi:
            L.append(f"\\nGÖRECELİ PERFORMANS ({tarih_str})")
            for ad, kaynak in [("HISSE", df), ("XU100", xu100_gecmis), ("XBANK", xbank_gecmis)]:
                if kaynak is None or kaynak.empty:
                    L.append(f"  {ad:<8} veri yok")
                    continue
                getiriler = []
                for gun, etiket in [(21, "1 Ay"), (63, "3 Ay"), (126, "6 Ay")]:
                    getiri = donem_getirisi(kaynak, gun)
                    getiriler.append(f"{etiket}: {getiri:+.2f}%" if getiri is not None else f"{etiket}: N/A")
                L.append(f"  {ad:<8} " + " | ".join(getiriler))

        L.append(f"\nKARŞILAŞTIRMA ({tarih_str})")
        if coin_mi:
            L.append(f"  Not          : Coinlerde endeks/kur karşılaştırması yapılmaz.")
        else:
            if xu100_deger:
                L.append(f"  XU100        : {xu100_deger:.2f} ({xu100_degisim:+.2f}%)")
            if usdtry_deger:
                L.append(f"  USD/TRY      : {usdtry_deger:.4f}")

        L.append("\n" + "=" * 50)
        L.append(f"  VERİ ÇEKİM ZAMANI: {cekim_zamani()}")
        L.append("=" * 50)

        return "\n".join(L)

    except Exception:
        return None

# ==================== TARAMA FONKSİYONU ====================
def tarama_yap(liste, liste_adi, periyot, bekleme=0.5):
    """Verilen hisse listesini tarar, sonuç metnini döndürür."""
    st.info(f"⏳ {liste_adi} taranıyor... Bu işlem {len(liste) * bekleme / 60:.1f} dakika sürebilir.")
    ilerleme = st.progress(0)
    durum = st.empty()

    tum_metinler = []
    basarili = 0
    basarisiz = []

    for i, sembol in enumerate(liste):
        durum.text(f"📊 {sembol} çekiliyor... {i+1}/{len(liste)}")
        metin = analiz_et(sembol, periyot)
        if metin:
            tum_metinler.append(metin)
            basarili += 1
        else:
            basarisiz.append(sembol)
        ilerleme.progress((i + 1) / len(liste))
        time.sleep(bekleme)

    durum.empty()
    ilerleme.empty()

    if not tum_metinler:
        st.error("❌ Hiçbir hisseden veri alınamadı.")
        return

    zaman = cekim_zamani()
    baslik = (
        "=" * 50 + "\n"
        f"  {liste_adi} - TOPLU ANALİZ\n"
        f"  Veri çekim zamanı: {zaman}\n"
        f"  Başarılı: {basarili}/{len(liste)}\n"
        + "=" * 50 + "\n\n"
    )
    son_not = (
        "\n\n" + "=" * 50 + "\n"
        f"  TARAMA BİTİŞ - VERİ ÇEKİM ZAMANI: {zaman}\n"
        + "=" * 50
    )
    tam_metin = baslik + "\n\n".join(tum_metinler) + son_not

    if basarisiz:
        st.warning(f"⚠️ Veri alınamayan hisseler: {', '.join(basarisiz)}")

    st.success(f"✅ {liste_adi} taraması tamam! ({basarili}/{len(liste)} hisse)")
    st.info("👇 Sağ üstteki **kopyala ikonuna** tıkla, sonra yapay zekaya yapıştır.")
    md_indir_butonu(f"{liste_adi} Toplu Analiz", tam_metin,
                    liste_adi.replace(" ", ""), f"md_{liste_adi}")
    st.code(tam_metin, language=None)

# ==================== GİRİŞ ====================
col1, col2 = st.columns([3, 1])
with col1:
    sembol_input = st.text_input("Hisse / Coin Sembolü", value="AKBNK",
                                 placeholder="Örn: AKBNK, KCHOL, BTC, ETH, SOL")
with col2:
    periyot = st.selectbox("Periyot", ["1y", "2y", "5y"], index=1)

analiz_btn   = st.button("🔍 Tek Hisse / Coin Analiz Et", type="primary", use_container_width=True)
bist30_btn   = st.button("📊 BIST 30'u Tara", use_container_width=True)
bist100_btn  = st.button("📊 BIST 100'ü Tara", use_container_width=True)

# ==================== TEK HİSSE / COİN ====================
if analiz_btn and sembol_input:
    with st.spinner(f"⏳ {sembol_input.upper()} verisi çekiliyor..."):
        sonuc = analiz_et(sembol_input, periyot)

    if sonuc is None:
        st.error(f"❌ {sembol_input.upper()} için veri alınamadı. Sembol doğru mu?")
    else:
        st.success(f"✅ {sembol_input.upper()} analizi hazır!")
        st.info("👇 Sağ üstteki **kopyala ikonuna** tıkla, sonra yapay zekaya yapıştır.")
        md_indir_butonu(f"{sembol_input.strip().upper()} Analiz", sonuc,
                        sembol_input.strip().upper(), "md_tek")
        st.code(sonuc, language=None)

# ==================== BIST 30 ====================
elif bist30_btn:
    tarama_yap(BIST30, "BIST 30", periyot, bekleme=0.3)

# ==================== BIST 100 ====================
elif bist100_btn:
    tarama_yap(BIST100, "BIST 100", periyot, bekleme=0.5)

else:
    if analiz_btn:
        st.warning("⚠️ Lütfen bir hisse veya coin sembolü gir.")
