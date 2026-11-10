# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta

import gostergeler as gst

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

# ==================== ENDEKS / KUR VERİSİ ====================
def endeksleri_cek(periyot):
    """XU100, XBANK ve USDTRY kapanış serilerini bir kez çeker. Alınamayan None olur."""
    kaynaklar = {"XU100": "XU100.IS", "XBANK": "XBANK.IS", "USDTRY": "USDTRY=X"}
    sonuc = {}
    for ad, sembol in kaynaklar.items():
        try:
            d = yf.Ticker(sembol).history(period=periyot, interval="1d")
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            sonuc[ad] = d["Close"].dropna() if not d.empty else None
        except Exception:
            sonuc[ad] = None
    return sonuc

# ==================== METİN BÖLÜMLERİ (yeni göstergeler) ====================
def _p(v):
    """Fiyat biçimi: 1'in altındaki coinlerde 4 hane."""
    return f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"

def _yon(b):
    return "N/A (veri yetersiz)" if b is None else ("YUKARI" if b else "AŞAĞI")

def bolum_para_akisi(df, info, coin_mi, tarih_str):
    cmf_v, mfi_v = df["CMF20"].iloc[-1], df["MFI14"].iloc[-1]
    cmf_et = ("para girişi" if cmf_v > 0.05 else "para çıkışı" if cmf_v < -0.05 else "nötr") if pd.notna(cmf_v) else ""
    mfi_et = ("aşırı alım" if mfi_v > 80 else "aşırı satım" if mfi_v < 20 else "nötr") if pd.notna(mfi_v) else ""
    L = [f"\nPARA GİRİŞİ / ÇIKIŞI ({tarih_str})",
         f"  CMF (20)     : {fmt(cmf_v)}  {cmf_et}",
         f"  MFI (14)     : {fmt(mfi_v)}  {mfi_et}"]
    if not coin_mi:
        L.append(f"  Kurumsal Sahip.: {fmt_yuzde(info.get('heldPercentInstitutions'))} (Yahoo, varsa)")
        L.append(f"  İçeriden Sahip.: {fmt_yuzde(info.get('heldPercentInsiders'))} (Yahoo, varsa)")
        L.append("  Not          : Kurum alım-satım (AKD) verisi Yahoo'da yok; CMF/MFI hacim bazlı tahmindir.")
    return L

def bolum_haftalik_aylik(df, tarih_str):
    d = gst.donem_kapanislari(df)
    son_tarih = gst.gunluk_indeks(df["Close"]).index[-1]
    son_fiyat = df["Close"].iloc[-1]

    def liste(seri, adet, fmt_tarih):
        L = []
        degisim = seri.pct_change() * 100
        for t in seri.index[-adet:]:
            devam = "  (devam ediyor)" if t > son_tarih else ""
            dg = degisim.loc[t]
            dg_s = f"{dg:+.2f}%" if pd.notna(dg) else "N/A"
            L.append(f"  {t.strftime(fmt_tarih):<12}{_p(seri.loc[t]):>10}  {dg_s:>8}{devam}")
        return L

    L = [f"\nHAFTALIK KAPANIŞ (son 5, Cuma) ({tarih_str})"]
    L += liste(d["hafta"], 5, "%d.%m.%Y")
    if pd.notna(d["h_ema21"]):
        L.append(f"  EMA 21 (H)   : {_p(d['h_ema21'])}  (fiyat {((son_fiyat/d['h_ema21']-1)*100):+.2f}%)")
    else:
        L.append("  EMA 21 (H)   : N/A (21 haftadan az veri)")
    if pd.notna(d["h_ema50"]):
        L.append(f"  EMA 50 (H)   : {_p(d['h_ema50'])}  (fiyat {((son_fiyat/d['h_ema50']-1)*100):+.2f}%)")
    else:
        L.append("  EMA 50 (H)   : N/A (50 haftadan az veri)")

    L.append(f"\nAYLIK KAPANIŞ (son 6) ({tarih_str})")
    L += liste(d["ay"], 6, "%m.%Y")
    if pd.notna(d["a_ema10"]):
        L.append(f"  EMA 10 (A)   : {_p(d['a_ema10'])}  (fiyat {((son_fiyat/d['a_ema10']-1)*100):+.2f}%)")
    else:
        L.append("  EMA 10 (A)   : N/A (10 aydan az veri)")

    yonler = [d["gunluk_yon"], d["haftalik_yon"], d["aylik_yon"]]
    mevcut = [y for y in yonler if y is not None]
    L.append(f"\nTREND UYUMU ({tarih_str})")
    L.append(f"  Günlük  (fiyat > EMA21)  : {_yon(d['gunluk_yon'])}")
    L.append(f"  Haftalık(fiyat > EMA21 H): {_yon(d['haftalik_yon'])}")
    L.append(f"  Aylık   (fiyat > EMA10 A): {_yon(d['aylik_yon'])}")
    L.append(f"  Uyum         : {sum(mevcut)}/{len(mevcut)} zaman diliminde YUKARI")
    return L

def bolum_goreceli(df, endeks_seri, ad, tarih_str):
    L = [f"\nGÖRECELİ PERFORMANS - {ad} KARŞISINDA ({tarih_str})"]
    if endeks_seri is None:
        return L + [f"  {ad} verisi alınamadı."]
    r = gst.goreceli_performans(df["Close"], endeks_seri)
    if r is None:
        return L + ["  Yeterli ortak veri yok."]
    L.append(f"  {'Periyot':<9}{'Hisse':>9}{ad:>9}{'Fark(puan)':>12}")
    for n, hg, eg, fark in r["getiri"]:
        L.append(f"  {str(n) + 'g':<9}{hg:>+8.2f}%{eg:>+8.2f}%{fark:>+12.2f}")
    rs20 = r["rs_degisim20"]
    L.append(f"  RS 20g değ.  : {fmt(rs20, '%') if pd.notna(rs20) else 'N/A'}")
    L.append(f"  RS trendi    : {'YUKARI (RS > RS EMA21)' if r['rs_trend_yukari'] else 'AŞAĞI (RS < RS EMA21)'}")
    return L

def bolum_destek_direnc(df, tarih_str):
    L = []
    for pencere, fraktal in [(60, 3), (20, 2)]:
        sd = gst.destek_direnc(df, pencere=pencere, fraktal=fraktal)
        L.append(f"\nDESTEK / DİRENÇ - SON {pencere} GÜN ({tarih_str})")
        if sd is None:
            L.append("  Veri yetersiz.")
            continue
        L.append(f"  {pencere}g Yüksek  : {_p(sd['yuksek'])}")
        L.append(f"  {pencere}g Düşük   : {_p(sd['dusuk'])}")
        for i, (s, t, u) in enumerate(sd["direnc"], 1):
            L.append(f"  Direnç {i}    : {_p(s)}  ({t} temas, {u:+.2f}%)")
        if not sd["direnc"]:
            L.append("  Direnç       : yok (fiyat pencere zirvesinde)")
        for i, (s, t, u) in enumerate(sd["destek"], 1):
            L.append(f"  Destek {i}    : {_p(s)}  ({t} temas, {u:+.2f}%)")
        if not sd["destek"]:
            L.append("  Destek       : yok (fiyat pencere dibinde)")
    return L

def bolum_hacim_profili(df, tarih_str, pencere=60):
    L = [f"\nHACİM PROFİLİ - SON {pencere} GÜN ({tarih_str})"]
    hp = gst.hacim_profili(df, pencere=pencere)
    if hp is None:
        return L + ["  Hesaplanamadı (veri yok veya fiyat sabit)."]
    kapanis = df["Close"].iloc[-1]
    konum = "değer alanı içinde" if hp["val"] <= kapanis <= hp["vah"] else (
        "değer alanının ÜSTÜNDE" if kapanis > hp["vah"] else "değer alanının ALTINDA")
    poc_i = int(np.argmax(hp["yuzde"]))
    L.append(f"  POC (en yoğun): {_p(hp['poc_alt'])} - {_p(hp['poc_ust'])}  (%{hp['yuzde'][poc_i]:.1f} hacim)")
    L.append(f"  Değer alanı %70: {_p(hp['val'])} - {_p(hp['vah'])}")
    L.append(f"  Fiyat konumu : {konum}")
    L.append("  En yoğun 5 bant (fiyata göre yüksekten düşüğe):")
    en_yogun = sorted(np.argsort(hp["yuzde"])[-5:], reverse=True)
    for i in en_yogun:
        bar = "█" * max(1, int(round(hp["yuzde"][i])))
        L.append(f"    {_p(hp['kenar'][i]):>10} - {_p(hp['kenar'][i+1]):<10} %{hp['yuzde'][i]:>5.1f} {bar}")
    return L

# ==================== HİSSE / COİN ANALİZİ ====================
def analiz_et(sembol_ham, periyot="2y", endeksler=None):
    """Hisse veya coin için tam analiz metni döndürür. Hata olursa None döner.

    endeksler: endeksleri_cek() sonucu. Taramada bir kez çekilip verilir; verilmezse (hisse için) burada çekilir.
    """
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
        try:
            info = hisse.info
        except Exception:
            info = {}

        if df.empty or len(df) < 60:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

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
        df["CMF20"]    = gst.cmf(df, 20)
        df["MFI14"]    = gst.mfi(df, 14)

        son    = df.iloc[-1]
        onceki = df.iloc[-2]
        tarih_str = df.index[-1].strftime("%d.%m.%Y")

        # XU100, XBANK ve USDTRY (sadece hisseler için; taramada dışarıdan hazır gelir)
        xu100_deger, xu100_degisim = None, None
        usdtry_deger = None
        xu100_seri = xbank_seri = None

        if not coin_mi:
            if endeksler is None:
                endeksler = endeksleri_cek(periyot)
            xu100_seri = endeksler.get("XU100")
            xbank_seri = endeksler.get("XBANK")
            usdtry_seri = endeksler.get("USDTRY")
            if xu100_seri is not None and len(xu100_seri) >= 2:
                xu100_degisim = (xu100_seri.iloc[-1] / xu100_seri.iloc[-2] - 1) * 100
                xu100_deger = xu100_seri.iloc[-1]
            if usdtry_seri is not None and len(usdtry_seri) >= 1:
                usdtry_deger = usdtry_seri.iloc[-1]

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
        L += bolum_para_akisi(df, info, coin_mi, tarih_str)

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

        L += bolum_haftalik_aylik(df, tarih_str)
        L += bolum_destek_direnc(df, tarih_str)
        L += bolum_hacim_profili(df, tarih_str, pencere=60)

        L.append(f"\nKARŞILAŞTIRMA ({tarih_str})")
        if coin_mi:
            L.append(f"  Not          : Coinlerde endeks/kur karşılaştırması yapılmaz.")
        else:
            if xu100_deger:
                L.append(f"  XU100        : {xu100_deger:.2f} ({xu100_degisim:+.2f}%)")
            if usdtry_deger:
                L.append(f"  USD/TRY      : {usdtry_deger:.4f}")
            L += bolum_goreceli(df, xu100_seri, "XU100", tarih_str)
            if sembol.replace(".IS", "") in gst.BANKA_HISSELERI:
                L += bolum_goreceli(df, xbank_seri, "XBANK", tarih_str)
            else:
                L.append("\n  Not          : XBANK kıyası yalnızca banka hisselerinde yapılır.")

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

    # XU100 / XBANK / USDTRY tüm tarama için bir kez çekilir (hisse başına 3 istek tasarrufu)
    endeksler = endeksleri_cek(periyot)

    for i, sembol in enumerate(liste):
        durum.text(f"📊 {sembol} çekiliyor... {i+1}/{len(liste)}")
        metin = analiz_et(sembol, periyot, endeksler)
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
