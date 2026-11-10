# -*- coding: utf-8 -*-
"""Saf pandas/numpy hesapları. Streamlit'e bağımlı değildir, panel.py'den bağımsız test edilir."""
import numpy as np
import pandas as pd

# XBANK (BIST Banka) endeksiyle kıyaslanacak banka hisseleri
BANKA_HISSELERI = {
    "AKBNK", "GARAN", "ISCTR", "VAKBN", "YKBNK",
    "HALKB", "TSKB", "SKBNK", "ALBRK",
}


def gunluk_indeks(seri):
    """Saat dilimini kaldırıp tarihe indirger (farklı borsaların serilerini hizalamak için)."""
    s = seri.copy()
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")]


# ==================== 2) PARA AKIŞI ====================
def cmf(df, n=20):
    """Chaikin Money Flow: +1'e yakın = para girişi, -1'e yakın = para çıkışı."""
    aralik = (df["High"] - df["Low"]).replace(0, np.nan)
    carpan = (((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / aralik).fillna(0)
    hacim = df["Volume"].rolling(n).sum().replace(0, np.nan)
    return (carpan * df["Volume"]).rolling(n).sum() / hacim


def mfi(df, n=14):
    """Money Flow Index (hacim ağırlıklı RSI): >80 aşırı alım, <20 aşırı satım."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    ham = tp * df["Volume"]
    fark = tp.diff()
    pozitif = ham.where(fark > 0, 0.0).rolling(n).sum()
    negatif = ham.where(fark < 0, 0.0).rolling(n).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        return 100 - 100 / (1 + pozitif / negatif)


# ==================== 1) HAFTALIK / AYLIK ====================
def donem_kapanislari(df):
    """Günlük veriden haftalık (Cuma) ve aylık kapanışlar + trend uyumu bayrakları."""
    c = gunluk_indeks(df["Close"]).dropna()
    hafta = c.resample("W-FRI").last().dropna()
    try:
        ay = c.resample("ME").last().dropna()
    except ValueError:  # eski pandas
        ay = c.resample("M").last().dropna()

    def son_ema(seri, span, min_bar):
        if len(seri) < min_bar:
            return np.nan
        return float(seri.ewm(span=span, adjust=False).mean().iloc[-1])

    son = float(c.iloc[-1])
    g_ema21 = float(c.ewm(span=21, adjust=False).mean().iloc[-1])
    h_ema21 = son_ema(hafta, 21, 21)
    h_ema50 = son_ema(hafta, 50, 50)
    a_ema10 = son_ema(ay, 10, 10)

    def yon(ema):
        if ema is None or np.isnan(ema):
            return None
        return son > ema

    return {
        "hafta": hafta, "ay": ay,
        "h_ema21": h_ema21, "h_ema50": h_ema50, "a_ema10": a_ema10,
        "gunluk_yon": yon(g_ema21), "haftalik_yon": yon(h_ema21), "aylik_yon": yon(a_ema10),
    }


# ==================== 3) GÖRECELİ PERFORMANS ====================
def goreceli_performans(hisse_kapanis, endeks_kapanis, gunler=(5, 20, 60, 120), rs_ema=21):
    """Hisse getirisi - endeks getirisi (puan) ve RS (hisse/endeks) trendi. Veri yetersizse None."""
    h = gunluk_indeks(hisse_kapanis)
    e = gunluk_indeks(endeks_kapanis).sort_index()
    e = e.reindex(h.index, method="ffill")
    cift = pd.concat([h, e], axis=1, keys=["h", "e"]).dropna()
    if len(cift) < 6:
        return None
    satirlar = []
    for n in gunler:
        if len(cift) > n:
            hg = (cift["h"].iloc[-1] / cift["h"].iloc[-1 - n] - 1) * 100
            eg = (cift["e"].iloc[-1] / cift["e"].iloc[-1 - n] - 1) * 100
            satirlar.append((n, hg, eg, hg - eg))
    rs = cift["h"] / cift["e"]
    rs_ema_son = rs.ewm(span=rs_ema, adjust=False).mean().iloc[-1]
    rs_degisim20 = (rs.iloc[-1] / rs.iloc[-21] - 1) * 100 if len(rs) > 20 else np.nan
    return {
        "getiri": satirlar,
        "rs_degisim20": float(rs_degisim20),
        "rs_trend_yukari": bool(rs.iloc[-1] > rs_ema_son),
    }


# ==================== 4) DESTEK / DİRENÇ ====================
def destek_direnc(df, pencere=60, fraktal=2, adet=3):
    """Son `pencere` gündeki pivot tepe/diplerden, yakın olanları kümeleyerek seviye çıkarır.

    Her seviye: (fiyat, temas sayısı, fiyata uzaklık %). Fiyatın altı destek, üstü dirençtir.
    """
    sub = df.tail(pencere)
    if len(sub) < 2 * fraktal + 1:
        return None
    H = sub["High"].to_numpy(dtype=float)
    L = sub["Low"].to_numpy(dtype=float)
    kapanis = float(sub["Close"].iloc[-1])

    adaylar = []
    for i in range(fraktal, len(sub) - fraktal):
        if np.isfinite(H[i]) and H[i] >= np.nanmax(H[i - fraktal:i + fraktal + 1]):
            adaylar.append(H[i])
        if np.isfinite(L[i]) and L[i] <= np.nanmin(L[i - fraktal:i + fraktal + 1]):
            adaylar.append(L[i])

    ort_aralik = float(np.nanmean((H - L)[-14:]))
    tol = max(0.5 * ort_aralik, 0.004 * kapanis)

    kumeler = []
    for s in sorted(adaylar):
        if kumeler and abs(s - np.mean(kumeler[-1])) <= tol:
            kumeler[-1].append(s)
        else:
            kumeler.append([s])
    seviyeler = [(float(np.mean(k)), len(k)) for k in kumeler]

    def satir(seviye, temas):
        return (seviye, temas, (seviye / kapanis - 1) * 100)

    destek = sorted([x for x in seviyeler if x[0] <= kapanis], key=lambda x: -x[0])[:adet]
    direnc = sorted([x for x in seviyeler if x[0] > kapanis], key=lambda x: x[0])[:adet]
    return {
        "destek": [satir(*x) for x in destek],
        "direnc": [satir(*x) for x in direnc],
        "yuksek": float(np.nanmax(H)),
        "dusuk": float(np.nanmin(L)),
    }


# ==================== 5) HACİM PROFİLİ ====================
def hacim_profili(df, pencere=60, kutu=20, deger_alani=0.70):
    """Son `pencere` günün hacmini fiyat bantlarına dağıtır (her mumun hacmi High-Low arasına eşit yayılır).

    POC = en yoğun bant, VAH/VAL = hacmin %70'inin işlem gördüğü bölgenin üst/alt sınırı.
    """
    sub = df.tail(pencere)
    lo, hi = float(sub["Low"].min()), float(sub["High"].max())
    if not (np.isfinite(lo) and np.isfinite(hi) and hi > lo):
        return None
    kenar = np.linspace(lo, hi, kutu + 1)
    hacim = np.zeros(kutu)
    for h, l, v in zip(sub["High"], sub["Low"], sub["Volume"]):
        if not (np.isfinite(h) and np.isfinite(l) and np.isfinite(v)) or v <= 0:
            continue
        if h <= l:
            i = int(np.clip(np.searchsorted(kenar, l, side="right") - 1, 0, kutu - 1))
            hacim[i] += v
            continue
        ortusme = np.clip(np.minimum(h, kenar[1:]) - np.maximum(l, kenar[:-1]), 0, None)
        toplam_ort = ortusme.sum()
        if toplam_ort > 0:
            hacim += v * ortusme / toplam_ort
    toplam = hacim.sum()
    if toplam <= 0:
        return None

    poc = int(hacim.argmax())
    alt = ust = poc
    alan = hacim[poc]
    while alan < deger_alani * toplam and (alt > 0 or ust < kutu - 1):
        alt_sonraki = hacim[alt - 1] if alt > 0 else -1.0
        ust_sonraki = hacim[ust + 1] if ust < kutu - 1 else -1.0
        if ust_sonraki >= alt_sonraki:
            ust += 1
            alan += hacim[ust]
        else:
            alt -= 1
            alan += hacim[alt]
    return {
        "kenar": kenar,
        "yuzde": hacim / toplam * 100,
        "poc_alt": float(kenar[poc]), "poc_ust": float(kenar[poc + 1]),
        "poc": float((kenar[poc] + kenar[poc + 1]) / 2),
        "val": float(kenar[alt]), "vah": float(kenar[ust + 1]),
    }
