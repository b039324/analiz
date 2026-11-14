# -*- coding: utf-8 -*-
"""Tarama sonuçlarını Excel benzeri tabloya (başlıklar üstte, açıklamalar altta) ve CSV'ye çevirir.

Streamlit'e bağımlı değildir; test_tablo.py ile test edilir.
"""
import csv
import io

import numpy as np
import pandas as pd

import gostergeler as gst

# (sütun başlığı, açıklama). Sıra = tablodaki sütun sırası.
SUTUNLAR = [
    ("Sembol", "Hisse/coin kodu."),
    ("Tarih", "Verideki son işlem gününün tarihi (son mum; piyasa açıksa gün içi, eksik mum olabilir)."),
    ("Kapanış", "Son kapanış (veya anlık) fiyat."),
    ("Değişim %", "Son mumun bir önceki kapanışa göre yüzde değişimi."),
    ("RSI 14", "14 günlük göreceli güç endeksi (basit ortalama yöntemi). 70 üstü aşırı alım, 30 altı aşırı satım bölgesi."),
    ("MACD Hist", "MACD çizgisi - sinyal çizgisi. Pozitif = momentum yukarı, negatif = aşağı."),
    ("Stoch %K", "14 günlük stokastik %K. 80 üstü aşırı alım, 20 altı aşırı satım bölgesi."),
    ("ADX 14", "Trend gücü (yön vermez). 25 üstü güçlü trend, 20 altı zayıf/yatay."),
    ("+DI", "Yukarı yön göstergesi. +DI > -DI ise alıcılar baskın."),
    ("-DI", "Aşağı yön göstergesi. -DI > +DI ise satıcılar baskın."),
    ("ATR %", "14 günlük ortalama gerçek aralığın fiyata oranı. Günlük oynaklığın yaklaşık büyüklüğü."),
    ("EMA21 Uzaklık %", "Fiyatın 21 günlük EMA'dan yüzde uzaklığı (+ = üstünde)."),
    ("EMA50 Uzaklık %", "Fiyatın 50 günlük EMA'dan yüzde uzaklığı."),
    ("EMA200 Uzaklık %", "Fiyatın 200 günlük EMA'dan yüzde uzaklığı. Boş = yeterli veri yok."),
    ("BB Genişlik %", "Bollinger bant genişliği (üst-alt)/orta. Düşük değer sıkışma anlamına gelir."),
    ("Hacim Oranı", "Son mum hacmi / 20 günlük ortalama hacim. 1'in üstü ortalamadan yüksek hacim."),
    ("CMF 20", "Chaikin Para Akışı (-1..+1). +0.05 üstü para girişi, -0.05 altı para çıkışı yönünde."),
    ("MFI 14", "Hacim ağırlıklı RSI (0..100). 80 üstü aşırı alım, 20 altı aşırı satım."),
    ("Günlük Yön", "Fiyat günlük EMA21'in üstündeyse YUKARI, altındaysa AŞAĞI."),
    ("Haftalık Yön", "Fiyat haftalık EMA21'in üstündeyse YUKARI, altındaysa AŞAĞI. Boş = 21 haftadan az veri."),
    ("Aylık Yön", "Fiyat aylık EMA10'un üstündeyse YUKARI, altındaysa AŞAĞI. Boş = 10 aydan az veri."),
    ("Trend Skoru", "Günlük, haftalık ve aylık yönlerden kaçı YUKARI (0-3). Boş yönler sayılmaz."),
    ("52h Konum %", "Son 252 işlem gününün dip-tepe aralığında fiyatın yeri (0 = dip, 100 = tepe). Coinde 252 gün ≈ 8 ay."),
    ("Direnç 1", "Son 60 günde fiyatın üstündeki en yakın direnç seviyesi (pivot tepelerin kümelenmesi)."),
    ("Direnç 1 Uzaklık %", "Fiyattan Direnç 1'e yüzde uzaklık."),
    ("Destek 1", "Son 60 günde fiyatın altındaki en yakın destek seviyesi (pivot diplerin kümelenmesi)."),
    ("Destek 1 Uzaklık %", "Fiyattan Destek 1'e yüzde uzaklık (negatif)."),
    ("Hacim POC", "Son 60 günde en çok hacmin işlem gördüğü fiyat bandının ortası."),
    ("Değer Alanı Alt", "Son 60 günde hacmin %70'inin gerçekleştiği bölgenin alt sınırı."),
    ("Değer Alanı Üst", "Son 60 günde hacmin %70'inin gerçekleştiği bölgenin üst sınırı."),
    ("Hacim Konumu", "Fiyat değer alanının ÜSTÜNDE, İÇİNDE veya ALTINDA."),
    ("XU100 20g Fark", "Son 20 günde hisse getirisi - BIST 100 getirisi (yüzde puan). Pozitif = endeksi geçiyor."),
    ("XU100 60g Fark", "Son 60 günde hisse getirisi - BIST 100 getirisi (yüzde puan)."),
    ("XU100 RS Trend", "Hisse/BIST100 oranı kendi 21 günlük EMA'sının üstündeyse YUKARI (endekse göre güçleniyor)."),
    ("XBANK 20g Fark", "Yalnızca banka hisselerinde: son 20 günde hisse getirisi - XBANK getirisi (puan)."),
    ("XBANK 60g Fark", "Yalnızca banka hisselerinde: son 60 günde hisse getirisi - XBANK getirisi (puan)."),
    ("Piyasa Değeri (milyon TL)", "Yahoo Finance piyasa değeri. Boş = veri yok."),
    ("F/K", "Fiyat/Kazanç (son 12 ay). Boş = veri yok."),
    ("PD/DD", "Piyasa Değeri / Defter Değeri. Boş = veri yok."),
    ("FD/FAVÖK", "Firma değeri / FAVÖK. Boş = veri yok."),
    ("ROE %", "Özkaynak kârlılığı (yüzde). Boş = veri yok."),
    ("Şirket", "Şirket adı (Yahoo Finance)."),
    ("Sektör", "Sektör (Yahoo Finance)."),
    ("Çekim Zamanı", "Verinin çekildiği an (İstanbul saati)."),
]
BASLIKLAR = [b for b, _ in SUTUNLAR]
ACIKLAMA = dict(SUTUNLAR)

DOGRULAMA_NOTU = (
    "Veriler Yahoo Finance'ten alınır; BIST verisi gecikmeli olabilir. Göstergeler bilgi amaçlıdır, "
    "yatırım tavsiyesi değildir."
)


# ---------- yardımcılar ----------
def _f(v, nd=2):
    try:
        if v is None:
            return None
        v = float(v)
        return None if np.isnan(v) or np.isinf(v) else round(v, nd)
    except (TypeError, ValueError):
        return None


def _fiyat(v):
    v = _f(v, 6)
    if v is None:
        return None
    return round(v, 4) if abs(v) < 1 else round(v, 2)


def _yon(b):
    return None if b is None else ("YUKARI" if b else "AŞAĞI")


def _uzaklik_pct(df, kolon):
    """Son fiyatın ilgili EMA'ya yüzde uzaklığı; veri yoksa None."""
    ema = df[kolon].iloc[-1]
    return _f((df["Close"].iloc[-1] / ema - 1) * 100) if pd.notna(ema) and ema else None


# ---------- satır hesabı ----------
def satir_hesapla(sembol, df, info, coin_mi, endeksler, zaman):
    """Göstergeleri hesaplanmış df'in son durumundan tek satırlık (başlık -> değer) sözlük üretir."""
    son, onceki = df.iloc[-1], df.iloc[-2]
    info = info or {}
    s = {
        "Sembol": sembol.replace(".IS", ""),
        "Tarih": df.index[-1].strftime("%d.%m.%Y"),
        "Kapanış": _fiyat(son["Close"]),
        "Değişim %": _f((son["Close"] / onceki["Close"] - 1) * 100),
        "RSI 14": _f(son["RSI"]),
        "MACD Hist": _f(son["MACD_Hist"], 3),
        "Stoch %K": _f(son["Stoch_K"]),
        "ADX 14": _f(son["ADX"]),
        "+DI": _f(son["PLUS_DI"]),
        "-DI": _f(son["MINUS_DI"]),
        "ATR %": _f(son["ATR_Pct"]),
        "EMA21 Uzaklık %": _uzaklik_pct(df, "EMA21"),
        "EMA50 Uzaklık %": _uzaklik_pct(df, "EMA50"),
        "EMA200 Uzaklık %": _uzaklik_pct(df, "EMA200"),
        "BB Genişlik %": _f(son["BB_Width"]),
        "Hacim Oranı": _f(son["Volume"] / son["Vol_MA20"]) if son["Vol_MA20"] else None,
        "CMF 20": _f(son["CMF20"], 3),
        "MFI 14": _f(son["MFI14"]),
    }

    # günlük / haftalık / aylık trend
    d = gst.donem_kapanislari(df)
    yonler = [d["gunluk_yon"], d["haftalik_yon"], d["aylik_yon"]]
    s["Günlük Yön"], s["Haftalık Yön"], s["Aylık Yön"] = (_yon(y) for y in yonler)
    s["Trend Skoru"] = sum(1 for y in yonler if y)

    y52, d52 = df["High"].tail(252).max(), df["Low"].tail(252).min()
    s["52h Konum %"] = _f((son["Close"] - d52) / (y52 - d52) * 100, 1) if y52 > d52 else None

    # destek / direnç (60g)
    sd = gst.destek_direnc(df, pencere=60, fraktal=3)
    if sd:
        if sd["direnc"]:
            s["Direnç 1"], s["Direnç 1 Uzaklık %"] = _fiyat(sd["direnc"][0][0]), _f(sd["direnc"][0][2])
        if sd["destek"]:
            s["Destek 1"], s["Destek 1 Uzaklık %"] = _fiyat(sd["destek"][0][0]), _f(sd["destek"][0][2])

    # hacim profili (60g)
    hp = gst.hacim_profili(df, pencere=60)
    if hp:
        s["Hacim POC"], s["Değer Alanı Alt"], s["Değer Alanı Üst"] = _fiyat(hp["poc"]), _fiyat(hp["val"]), _fiyat(hp["vah"])
        k = son["Close"]
        s["Hacim Konumu"] = "İÇİNDE" if hp["val"] <= k <= hp["vah"] else ("ÜSTÜNDE" if k > hp["vah"] else "ALTINDA")

    if not coin_mi:
        endeksler = endeksler or {}

        def fark_sutunlari(seri):
            return None if seri is None else gst.goreceli_performans(df["Close"], seri)

        g = fark_sutunlari(endeksler.get("XU100"))
        if g:
            farklar = {n: fark for n, _, _, fark in g["getiri"]}
            s["XU100 20g Fark"], s["XU100 60g Fark"] = _f(farklar.get(20)), _f(farklar.get(60))
            s["XU100 RS Trend"] = _yon(g["rs_trend_yukari"])
        if sembol.replace(".IS", "") in gst.BANKA_HISSELERI:
            gb = fark_sutunlari(endeksler.get("XBANK"))
            if gb:
                farklar = {n: fark for n, _, _, fark in gb["getiri"]}
                s["XBANK 20g Fark"], s["XBANK 60g Fark"] = _f(farklar.get(20)), _f(farklar.get(60))

        pd_ = info.get("marketCap")
        s["Piyasa Değeri (milyon TL)"] = _f(pd_ / 1e6, 0) if isinstance(pd_, (int, float)) else None
        s["F/K"] = _f(info.get("trailingPE"))
        s["PD/DD"] = _f(info.get("priceToBook"))
        s["FD/FAVÖK"] = _f(info.get("enterpriseToEbitda"))
        roe = info.get("returnOnEquity")
        s["ROE %"] = _f(roe * 100, 1) if isinstance(roe, (int, float)) else None
        s["Şirket"] = info.get("longName")
        s["Sektör"] = info.get("sector")

    s["Çekim Zamanı"] = zaman
    return s


# ---------- tablo ----------
def tablo_olustur(satirlar):
    """Satır sözlüklerinden DataFrame. Sütun sırası SUTUNLAR'a göre; hiçbir satırda verisi olmayan sütunlar atılır."""
    df = pd.DataFrame(satirlar)
    df = df.reindex(columns=BASLIKLAR).dropna(axis=1, how="all")
    return df.reset_index(drop=True)


def aciklama_tablosu(df):
    """Tabloda bulunan sütunların açıklamaları (tablonun altında gösterilir)."""
    return pd.DataFrame({"Sütun": list(df.columns), "Açıklama": [ACIKLAMA[c] for c in df.columns]})


# ---------- CSV ----------
def _guvenli(h):
    """Excel'in formül sanmaması için =,+,-,@ ile başlayan metinlerin başına ' koyar."""
    if isinstance(h, str) and h[:1] in ("=", "+", "-", "@"):
        return "'" + h
    return h


def csv_olustur(df, aciklamalar=True, bicim="tr", zaman=None):
    """CSV baytları (UTF-8 BOM'lu: Excel Türkçe karakterleri doğru açar).

    bicim="tr": ayırıcı ';' ondalık ','  (Türkçe Excel'de çift tıkla düzgün sütunlara açılır)
    bicim="uluslararasi": ayırıcı ',' ondalık '.'
    Sıra: başlık satırı, veri satırları, boş satır, AÇIKLAMALAR bölümü, veri çekim zamanı.
    """
    ayirac, ondalik = (";", ",") if bicim == "tr" else (",", ".")
    d = df.copy()
    for c in d.columns:
        if not pd.api.types.is_numeric_dtype(d[c]):   # metin sütunları (object veya pandas 3 'str')
            d[c] = d[c].map(_guvenli)
    tampon = io.StringIO()
    d.to_csv(tampon, index=False, sep=ayirac, decimal=ondalik, lineterminator="\r\n")
    w = csv.writer(tampon, delimiter=ayirac, lineterminator="\r\n")
    if aciklamalar:
        w.writerow([])
        w.writerow(["AÇIKLAMALAR"])
        w.writerow(["Sütun", "Açıklama"])
        for c in df.columns:
            w.writerow([c, ACIKLAMA[c]])
        w.writerow(["Not", DOGRULAMA_NOTU])
    if zaman:
        w.writerow([])
        w.writerow(["VERİ ÇEKİM ZAMANI", zaman])
    return tampon.getvalue().encode("utf-8-sig")
