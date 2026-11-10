# -*- coding: utf-8 -*-
"""Çalıştır: python -m pytest test_gostergeler.py  (veya: python test_gostergeler.py)"""
import numpy as np
import pandas as pd

import gostergeler as g


def _df(close, high=None, low=None, vol=None, start="2026-01-01", tz="Europe/Istanbul"):
    close = pd.Series(close, dtype=float)
    idx = pd.bdate_range(start, periods=len(close), tz=tz)
    return pd.DataFrame({
        "Open": close.values,
        "High": (close + 1 if high is None else pd.Series(high, dtype=float)).values,
        "Low": (close - 1 if low is None else pd.Series(low, dtype=float)).values,
        "Close": close.values,
        "Volume": (np.full(len(close), 1000.0) if vol is None else np.asarray(vol, dtype=float)),
    }, index=idx)


def test_cmf_kapanis_hep_tepede_ise_1():
    c = np.arange(100, 140, dtype=float)
    df = _df(c, high=c, low=c - 2)  # kapanış = yüksek
    assert abs(g.cmf(df).iloc[-1] - 1.0) < 1e-9


def test_cmf_sinirlari():
    rng = np.random.default_rng(0)
    c = 100 + rng.normal(0, 1, 120).cumsum()
    v = g.cmf(_df(c)).dropna()
    assert v.between(-1, 1).all()


def test_mfi_surekli_yukselis_100_ve_sinirlar():
    assert g.mfi(_df(np.arange(100, 140))).iloc[-1] == 100
    rng = np.random.default_rng(1)
    c = 100 + rng.normal(0, 1, 150).cumsum()
    v = g.mfi(_df(c)).dropna()
    assert v.between(0, 100).all()


def test_donem_kapanislari_hafta_ve_ay():
    df = _df(np.arange(100, 100 + 300), start="2025-01-01")
    r = g.donem_kapanislari(df)
    # haftalık kapanış = o haftanın son iş günü kapanışı
    ilk_cuma = pd.Timestamp("2025-01-03")
    assert r["hafta"].iloc[0] == df["Close"].iloc[2] and r["hafta"].index[0] == ilk_cuma
    ocak_2025 = df.loc[(df.index.year == 2025) & (df.index.month == 1), "Close"]
    assert r["ay"].iloc[0] == ocak_2025.iloc[-1]
    assert r["gunluk_yon"] and r["haftalik_yon"] and r["aylik_yon"]  # sürekli yükseliş


def test_donem_kapanislari_kisa_veride_ema_nan():
    r = g.donem_kapanislari(_df(np.arange(100, 130)))
    assert np.isnan(r["h_ema50"]) and r["aylik_yon"] is None


def test_goreceli_performans_farkli_saat_dilimi():
    h = _df(np.linspace(100, 200, 130), tz="Europe/Istanbul")["Close"]      # hisse 2x
    e = _df(np.linspace(100, 110, 130), tz="Europe/London")["Close"]        # endeks %10
    r = g.goreceli_performans(h, e)
    n, hg, eg, fark = r["getiri"][-1]
    assert n == 120 and hg > eg and fark > 0 and r["rs_trend_yukari"]


def test_goreceli_performans_yetersiz_veri():
    s = _df(np.arange(100, 103))["Close"]
    assert g.goreceli_performans(s, s) is None


def test_destek_direnc_bilinen_seviyeler():
    # 100'e 3 kez dokunup dönen, 90'a 3 kez dokunup dönen yatay bant
    kapanis, yuksek, dusuk = [], [], []
    for _ in range(6):
        for c, h, l in [(95, 96, 94), (97, 99, 96), (100, 100, 98), (97, 99, 96),
                        (94, 95, 92), (91, 92, 90), (93, 94, 91), (96, 97, 94)]:
            kapanis.append(c); yuksek.append(h); dusuk.append(l)
    kapanis[-1] = 95
    r = g.destek_direnc(_df(kapanis, high=yuksek, low=dusuk), pencere=48)
    assert any(abs(s - 100) < 1 and t >= 3 for s, t, _ in r["direnc"])
    assert any(abs(s - 90) < 1 and t >= 3 for s, t, _ in r["destek"])
    assert all(u > 0 for _, _, u in r["direnc"]) and all(u <= 0 for _, _, u in r["destek"])


def test_destek_direnc_kisa_veri_none():
    assert g.destek_direnc(_df([1, 2, 3]), pencere=60) is None


def test_hacim_profili_yogunluk_bolgesi():
    # 100-102 arasında yoğun hacim, geri kalanı seyrek
    c = np.concatenate([np.full(40, 101.0), np.linspace(101, 120, 20)])
    v = np.concatenate([np.full(40, 5000.0), np.full(20, 100.0)])
    df = _df(c, high=c + 0.5, low=c - 0.5, vol=v)
    p = g.hacim_profili(df, pencere=60)
    assert abs(p["yuzde"].sum() - 100) < 1e-6
    assert 100 <= p["poc"] <= 102
    assert p["val"] <= p["poc"] <= p["vah"]


def test_hacim_profili_hacim_korunur():
    rng = np.random.default_rng(2)
    c = 100 + rng.normal(0, 1, 60).cumsum()
    df = _df(c, vol=rng.integers(100, 1000, 60))
    p = g.hacim_profili(df)
    assert abs(p["yuzde"].sum() - 100) < 1e-6


def test_hacim_profili_duz_fiyat_none():
    c = np.full(60, 100.0)
    assert g.hacim_profili(_df(c, high=c, low=c)) is None


if __name__ == "__main__":
    for ad, fn in list(globals().items()):
        if ad.startswith("test_"):
            fn()
            print("OK", ad)
