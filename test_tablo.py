# -*- coding: utf-8 -*-
"""Çalıştır: python -m pytest test_tablo.py"""
import csv
import io

import numpy as np
import pandas as pd

import gostergeler as gst
import tablo


def _ohlcv(seed=0, n=400, bas=100.0, tz="Europe/Istanbul"):
    rng = np.random.default_rng(seed)
    c = bas * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
    idx = pd.bdate_range(end="2026-11-09", periods=n, tz=tz)
    return pd.DataFrame({"Open": c * 0.998, "High": c * 1.01, "Low": c * 0.99, "Close": c,
                         "Volume": rng.integers(1_000_000, 9_000_000, n).astype(float)}, index=idx)


def _satir(sembol="AKBNK.IS", coin=False, info=None, seed=0):
    df = gst.teknik_gostergeler(_ohlcv(seed))
    end = {"XU100": _ohlcv(10, tz="Europe/Istanbul")["Close"], "XBANK": _ohlcv(11)["Close"]}
    return tablo.satir_hesapla(sembol, df, info, coin, end, "14.11.2026 16:40:00 (İstanbul)")


INFO = {"longName": "Test Bankası", "sector": "Financial Services", "marketCap": 250_000_000_000,
        "trailingPE": 4.5, "priceToBook": 1.2, "returnOnEquity": 0.35}


def test_basliklar_benzersiz_ve_aciklamali():
    assert len(tablo.BASLIKLAR) == len(set(tablo.BASLIKLAR))
    assert all(tablo.ACIKLAMA[b].strip() for b in tablo.BASLIKLAR)


def test_satir_anahtarlari_tanimli_basliklardan():
    s = _satir(info=INFO)
    assert set(s) <= set(tablo.BASLIKLAR)
    assert s["Sembol"] == "AKBNK" and s["Çekim Zamanı"].endswith("(İstanbul)")
    assert s["Piyasa Değeri (milyon TL)"] == 250000 and s["ROE %"] == 35.0
    assert s["Trend Skoru"] in (0, 1, 2, 3)           # '3/3' gibi Excel'in tarihe çevireceği metin yok
    assert "XBANK 20g Fark" in s                      # AKBNK banka hissesi


def test_banka_olmayan_hissede_xbank_yok_coinde_temel_ve_endeks_yok():
    assert "XBANK 20g Fark" not in _satir("ASELS.IS", info=INFO)
    c = _satir("BTC-USD", coin=True)
    assert not ({"F/K", "XU100 20g Fark", "Şirket"} & set(c))


def test_tablo_sutun_sirasi_ve_bos_sutunlar():
    df = tablo.tablo_olustur([_satir("AKBNK.IS", info=INFO), _satir("ASELS.IS", info=INFO, seed=3)])
    assert list(df.columns) == [b for b in tablo.BASLIKLAR if b in df.columns]
    assert df.columns[0] == "Sembol" and df.columns[-1] == "Çekim Zamanı"
    assert len(df) == 2
    assert pd.isna(df.loc[1, "XBANK 20g Fark"]) and pd.notna(df.loc[0, "XBANK 20g Fark"])
    coin = tablo.tablo_olustur([_satir("BTC-USD", coin=True)])
    assert "F/K" not in coin.columns and "Şirket" not in coin.columns   # tamamen boş sütunlar atılır


def test_aciklama_tablosu_sutunlarla_ayni():
    df = tablo.tablo_olustur([_satir(info=INFO)])
    a = tablo.aciklama_tablosu(df)
    assert list(a["Sütun"]) == list(df.columns) and a["Açıklama"].str.len().min() > 10


def _oku(b, ayirac):
    return list(csv.reader(io.StringIO(b.decode("utf-8-sig")), delimiter=ayirac))


def test_csv_tr_baslik_ustte_aciklama_altta():
    df = tablo.tablo_olustur([_satir("AKBNK.IS", info=INFO), _satir("ASELS.IS", info=INFO, seed=3)])
    ham = tablo.csv_olustur(df, aciklamalar=True, bicim="tr", zaman="14.11.2026 16:40:00 (İstanbul)")
    assert ham.startswith(b"\xef\xbb\xbf")                       # UTF-8 BOM
    satirlar = _oku(ham, ";")
    assert satirlar[0] == list(df.columns)                       # başlıklar en üstte
    assert satirlar[1][0] == "AKBNK" and satirlar[2][0] == "ASELS"
    assert satirlar[3] == []                                     # boş satır
    assert satirlar[4] == ["AÇIKLAMALAR"] and satirlar[5] == ["Sütun", "Açıklama"]
    assert [r[0] for r in satirlar[6:6 + len(df.columns)]] == list(df.columns)
    assert satirlar[-1] == ["VERİ ÇEKİM ZAMANI", "14.11.2026 16:40:00 (İstanbul)"]
    kapanis_i = satirlar[0].index("Kapanış")
    assert "," in satirlar[1][kapanis_i] and "." not in satirlar[1][kapanis_i]   # ondalık virgül


def test_csv_uluslararasi_ve_aciklamasiz():
    df = tablo.tablo_olustur([_satir(info=INFO)])
    ham = tablo.csv_olustur(df, aciklamalar=False, bicim="uluslararasi")
    satirlar = _oku(ham, ",")
    assert satirlar[0] == list(df.columns) and len(satirlar) == 2
    assert "AÇIKLAMALAR" not in ham.decode("utf-8-sig")
    assert "." in satirlar[1][satirlar[0].index("Kapanış")]


def test_csv_formul_enjeksiyonu_engellenir():
    s = _satir(info={**INFO, "longName": "=HYPERLINK(\"http://x\")"})
    df = tablo.tablo_olustur([s])
    satirlar = _oku(tablo.csv_olustur(df, aciklamalar=False), ";")
    assert satirlar[1][satirlar[0].index("Şirket")].startswith("'=")
