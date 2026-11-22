"""Bootstrap over years for the CORDEX resolution test: is the difference between the coarse and the fine grid in the change of low-wind spells per year larger than the sampling noise of 10 years per period?
Resamples the 10 years of each period (with replacement, 1000 draws), recomputes the regional mean change in spells per year on both grids and reports the difference (coarse minus fine) with a 90 percent interval.
Spells are counted inside each calendar year (a spell crossing 31 December is cut), so values differ slightly from cordex_resolution.csv."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import wp7_cordex_resolution as w

rng = np.random.default_rng(7)
H, F = w.load("historical"), w.load("rcp85")
rows = []
for name in w.REGIONS:
    uh, mask = H[name]; uf, _ = F[name]
    uh = np.where(mask[None], uh, np.nan); uf = np.where(mask[None], uf, np.nan)
    out = {}
    for tag, (a, b) in (("fine", (uh, uf)), ("coarse", (w.block_mean(uh, mask), w.block_mean(uf, mask)))):
        thr = np.nanpercentile(a, 10, axis=0)
        per = {}
        for ptag, u in (("h", a), ("f", b)):
            T = u.shape[0]; n_y = 10; L = T // n_y
            cnt = []
            for y in range(n_y):
                low = u[y * L:(y + 1) * L] <= thr[None]
                n, _ = w.spells(low)
                cnt.append(np.nanmean(n))
            per[ptag] = np.array(cnt)
        out[tag] = per
    ch = {t: out[t]["f"].mean() - out[t]["h"].mean() for t in out}
    diffs = []
    for _ in range(1000):
        ih, jf = rng.integers(0, 10, 10), rng.integers(0, 10, 10)
        d = {t: out[t]["f"][jf].mean() - out[t]["h"][ih].mean() for t in out}
        diffs.append((d["fine"], d["coarse"], d["coarse"] - d["fine"]))
    D = np.array(diffs)
    rows.append({"region": name, "change_fine": ch["fine"], "change_coarse": ch["coarse"],
                 "fine_p5": np.percentile(D[:, 0], 5), "fine_p95": np.percentile(D[:, 0], 95),
                 "coarse_p5": np.percentile(D[:, 1], 5), "coarse_p95": np.percentile(D[:, 1], 95),
                 "diff_coarse_minus_fine": ch["coarse"] - ch["fine"], "diff_p5": np.percentile(D[:, 2], 5), "diff_p95": np.percentile(D[:, 2], 95)})
r = pd.DataFrame(rows)
r.to_csv(w.OUT / "cordex_bootstrap.csv", index=False)
print(r.round(2).to_string())
