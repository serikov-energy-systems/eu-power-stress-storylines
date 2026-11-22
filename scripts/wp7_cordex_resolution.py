"""v0.4 WP6b: does regional climate model output (EURO-CORDEX, 0.11 degrees) change low-wind statistics where terrain matters?

Data: one EURO-CORDEX run (CNRM-CM5 driving CLMcom-ETH-COSMO-crCLIM-v1-1, EUR-11, daily mean 10 m wind sfcWind), historical
1996-2005 and RCP8.5 2091-2100, downloaded by scripts/download_cordex.py from the DKRZ ESGF node.
Method: the same wind series is converted to a capacity factor twice, (a) cell by cell at 0.11 degrees and (b) after averaging the
wind speed over boxes of 11 x 9 cells (about 1.25 x 0.94 degrees, the grid of CESM2 used by Climate2Energy). Statistics are
computed on both and compared: mean capacity factor, spells of at least two days below the historical 10th percentile, and the
change between the two periods. Three regions: Alps, Balkans (Dinaric Alps and Carpathian arc) and the North German plain as a flat control.
ASSUMED: 10 m to 129 m by a power law with exponent 0.143, a generic power curve (cut-in 3, rated 10.5, cut-out 25 m/s) applied to
DAILY mean wind (so absolute capacity factors are lower than from hourly data and are not comparable with Climate2Energy levels).
One RCM, one realization, ten years per period, RCP8.5 (Climate2Energy uses SSP3-7.0): differences in the change signal between the two
resolutions are what the test is about, not the absolute climate change.
"""
import json
import sys
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "z_data" / "z6_cordex" / "nc"
OUT = ROOT / "results" / "v04"
OUT.mkdir(parents=True, exist_ok=True)
REGIONS = {"Alps": (45.5, 47.8, 6.5, 13.5), "Balkans": (41.0, 45.0, 17.0, 26.0), "North German plain": (52.0, 54.0, 8.0, 14.0)}
BY, BX = 9, 11
ALPHA = 0.143


def cf(u):
    uh = u * (129.0 / 10.0) ** ALPHA
    c = np.clip(((uh - 3.0) / (10.5 - 3.0)) ** 3, 0, 1)
    return np.where((uh < 3.0) | (uh > 25.0), 0.0, c)


def load(period):
    files = sorted(NC.glob(f"sfcWind_*_{period}_*.nc"))
    assert files, f"no files for {period}"
    out = {}
    for name, (la0, la1, lo0, lo1) in REGIONS.items():
        parts, mask = [], None
        for f in files:
            ds = netCDF4.Dataset(f)
            lat, lon = ds["lat"][:], ds["lon"][:]
            m = (lat >= la0) & (lat <= la1) & (lon >= lo0) & (lon <= lo1)
            ys, xs = np.where(m)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            ny, nx = (y1 - y0) // BY * BY, (x1 - x0) // BX * BX
            u = ds["sfcWind"][:, y0:y0 + ny, x0:x0 + nx]
            parts.append(np.ma.filled(u, np.nan).astype("float32"))
            mask = m[y0:y0 + ny, x0:x0 + nx]
            ds.close()
        out[name] = (np.concatenate(parts, axis=0), mask)
    return out


def spells(low):
    """Number and mean length of runs of >= 2 consecutive True along axis 0, per cell."""
    T = low.shape[0]
    n = np.zeros(low.shape[1:], int)
    tot = np.zeros(low.shape[1:], int)
    run = np.zeros(low.shape[1:], int)
    for t in range(T + 1):
        cur = low[t] if t < T else np.zeros(low.shape[1:], bool)
        ended = (~cur) & (run >= 2)
        n += ended
        tot += np.where(ended, run, 0)
        run = np.where(cur, run + 1, 0)
    return n, np.where(n > 0, tot / np.maximum(n, 1), np.nan)


def block_mean(a, mask):
    T, ny, nx = a.shape
    a = np.where(mask[None], a, np.nan)
    b = a.reshape(T, ny // BY, BY, nx // BX, BX)
    with np.errstate(all="ignore"):
        return np.nanmean(b, axis=(2, 4))


def stats(cf_h, cf_f, years_h, years_f):
    thr = np.nanpercentile(cf_h, 10, axis=0)
    r = {}
    for tag, c, y in (("hist", cf_h, years_h), ("fut", cf_f, years_f)):
        low = c <= thr[None]
        n, dur = spells(low)
        r[tag] = {"mean_cf": np.nanmean(c, axis=0), "spells_yr": n / y, "dur": dur, "low_share": low.mean(axis=0)}
    return r


rows, spatial = [], []
H, F = load("historical"), load("rcp85")
yh, yf = 10, 10
for name in REGIONS:
    uh, mask = H[name]
    uf, _ = F[name]
    uh = np.where(mask[None], uh, np.nan)
    uf = np.where(mask[None], uf, np.nan)
    fine = stats(cf(uh), cf(uf), yh, yf)
    coarse = stats(cf(block_mean(uh, mask)), cf(block_mean(uf, mask)), yh, yf)
    for res, s in (("0.11 deg", fine), ("1.25 x 0.94 deg", coarse)):
        d = {k: float(np.nanmean(s["fut"][k]) - np.nanmean(s["hist"][k])) for k in ("mean_cf", "spells_yr", "low_share")}
        rows.append({"region": name, "resolution": res, "cells": int(np.isfinite(s["hist"]["mean_cf"]).sum()),
                     "mean_cf_hist": float(np.nanmean(s["hist"]["mean_cf"])), "mean_cf_fut": float(np.nanmean(s["fut"]["mean_cf"])),
                     "spells_per_yr_hist": float(np.nanmean(s["hist"]["spells_yr"])), "spells_per_yr_fut": float(np.nanmean(s["fut"]["spells_yr"])),
                     "spell_len_hist": float(np.nanmean(s["hist"]["dur"])), "spell_len_fut": float(np.nanmean(s["fut"]["dur"])),
                     "d_mean_cf": d["mean_cf"], "d_spells_yr": d["spells_yr"], "d_low_share": d["low_share"],
                     "spatial_sd_mean_cf_hist": float(np.nanstd(s["hist"]["mean_cf"])),
                     "spatial_sd_d_mean_cf": float(np.nanstd(s["fut"]["mean_cf"] - s["hist"]["mean_cf"]))})
res = pd.DataFrame(rows)
res.to_csv(OUT / "cordex_resolution.csv", index=False)
print(res.round(3).T.to_string())
