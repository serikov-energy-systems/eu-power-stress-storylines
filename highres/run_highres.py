"""v0.4: highRES on a stress window and a normal window (GAMS demo licence, HiGHS).

Needs: GAMS (demo licence is enough: the instance has fewer than 2000 rows) with gams.exe and gdxdump.exe, and a clone of
https://github.com/highRES-model/highRES (MIT licence). Set HIGHRES_SRC (clone) and GAMS_DIR. The instance is generated here
from the ERA5/C3S capacity factors and ENTSO-E load of this repository; costs, limits and transmission are ASSUMED.

    python highres/run_highres.py
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = Path(os.environ.get("HIGHRES_SRC", Path.home() / "z_data" / "z6" / "highRES"))
GAMS = Path(os.environ.get("GAMS_DIR", Path.home() / "tools" / "GAMS" / "54"))
WORK = Path(os.environ.get("HIGHRES_WORK", ROOT / "highres" / "work"))
WORK.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "results" / "v04"
OUT.mkdir(parents=True, exist_ok=True)
# windows: highest and median 84-hour mean net load of DE+FR in Nov-Feb 2020-2025 (fleet 70/100 GW DE, 25/25 GW FR wind/PV, assumed)
WINDOWS = {"stress": "2021-01-05 04:00", "normal": "2020-11-11 04:00"}
H = 84


def dump(gdx, name):
    txt = subprocess.run([str(GAMS / "gdxdump.exe"), str(gdx), f"symb={name}"], capture_output=True, text=True).stdout
    return {m[0]: float(m[1]) for m in re.findall(r"'([\w.']+)'(?:\.L)?\s+(-?[\d.eE+-]+)", txt.replace("'.'", "."))}


rows = []
for label, start in WINDOWS.items():
    d = WORK / label
    subprocess.run([sys.executable, str(HERE / "make_instance.py"), label, start, str(H)], check=True, env={**os.environ, "HIGHRES_WORK": str(WORK)})
    for f in SRC.glob("*.gms"):
        shutil.copy(f, d / f.name)
    subprocess.run([sys.executable, str(HERE / "patch_main.py"), str(d)], check=True)
    subprocess.run([str(GAMS / "gams.exe"), "highRES.gms", "lo=2"], cwd=d, check=True, capture_output=True)
    lst = (d / "highRES.lst").read_text(errors="ignore")
    status = re.search(r"MODEL STATUS\s+(\d+ \w+)", lst).group(1)
    obj = float(re.search(r"OBJECTIVE VALUE\s+([\d.eE+]+)", lst).group(1))
    gdx = d / f"hR_{label}.gdx"
    vre, nv, st = dump(gdx, "var_vre_cap"), dump(gdx, "var_non_vre_cap"), dump(gdx, "var_store_gen_cap")
    gen = dump(gdx, "non_vre_gen_tot")
    dem = float(pd.read_parquet(ROOT / "data" / "derived" / "entsoe_load.parquet")[["DE", "FR"]].loc[
        pd.Timestamp(start):pd.Timestamp(start) + pd.Timedelta(hours=H - 1)].sum().sum())
    rows.append({"window": label, "start": start, "hours": H, "status": status, "cost_meur_window": obj / 1e6, "demand_gwh": dem / 1e3,
                 "wind_gw": vre.get("Wind", 0) / 1e3, "solar_gw": vre.get("Solar", 0) / 1e3, "gas_gw": nv.get("Gas", 0) / 1e3,
                 "nuclear_gw": nv.get("Nuclear", 0) / 1e3, "battery_gw": st.get("Battery", 0) / 1e3,
                 "gas_share": gen.get("Gas", 0) / (dem or 1), "pgen_gw": nv.get("pgen", 0) / 1e3})
    print(rows[-1], flush=True)
df = pd.DataFrame(rows)
df["cost_eur_per_mwh"] = df.cost_meur_window * 1e6 / (df.demand_gwh * 1e3)
df.to_csv(OUT / "highres_windows.csv", index=False)
print(df.round(2).T)
