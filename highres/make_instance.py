"""Build the input files (.dd) of a small highRES instance from the data of eu-stress-events.

Zones: DE, FR (one region each). One window (H hours, demo licence limit of 2000 rows) of ERA5/C3S wind and PV capacity factors and ENTSO-E load.
Everything else (costs, capacity limits, transmission) is ASSUMED and stylised; capital costs are annualised costs scaled to the
week (168/8760). Usage: python make_instance.py <label> <start timestamp>
"""
import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "data" / "derived"
ZONES = ["DE", "FR"]
label, start = sys.argv[1], pd.Timestamp(sys.argv[2])
H = int(sys.argv[3]) if len(sys.argv) > 3 else 96
out = Path(__import__("os").environ.get("HIGHRES_WORK", ".")) / label
out.mkdir(exist_ok=True)
idx = pd.date_range(start, periods=H, freq="h")
wind = pd.read_parquet(SRC / "c3s_wind_on.parquet")[ZONES].reindex(idx).clip(0, 1)
pv = pd.read_parquet(SRC / "c3s_pv.parquet")[ZONES].reindex(idx).clip(0, 1)
load = pd.read_parquet(SRC / "entsoe_load.parquet")[ZONES].reindex(idx)
assert not (wind.isna().any().any() or pv.isna().any().any() or load.isna().any().any()), "missing data"
hours = [str(i) for i in range(0, H + 1)]
WEEK = H / 8760.0  # share of the year


def w(name, lines):
    (out / name).write_text("\n".join(lines) + "\n", encoding="ascii")


w("tstep_x.dd", hours)
w("regions.dd", ZONES)
w("zones.dd", ZONES)
vre, nonvre = ["Wind", "Solar"], ["Gas", "Nuclear", "pgen"]
w("generator_all.dd", vre + nonvre)
w("generator_vre.dd", vre)
w("generator_nonvre.dd", nonvre)
w("transmission_all.dd", ["HVAC"])
links = [("DE", "FR", 900)]
w("transmission_links.dd", [f"{a}.{b}.HVAC" for a, b, _ in links])
w("transmission_links_cap.dd", [f"{a}.{b}.HVAC {c}" for a, b, c in links])
w("transmission_links_dist.dd", ["DE.FR.HVAC 600"])
# non-VRE capacity limits in GW per zone (assumed)
lim = {"Gas": {"DE": 120, "FR": 100, }, "Nuclear": {"DE": 0.001, "FR": 55}, "pgen": {z: 400 for z in ZONES}}
w("generator_lim_x.dd", [f"{z}.{g} {v}" for z, g in [(z, g) for g in nonvre for z in ZONES] for v in [lim[g][z]]])
# buildable area (km2) and MW per km2 (assumed)
area = {"Wind": {"DE": 40000, "FR": 80000}, "Solar": {"DE": 30000, "FR": 40000}}
w("vre_areas_x_agg_x.dd", [f"{g}.{z}.{z} {area[g][z]}" for g in vre for z in ZONES])
w("generator_cap2area.dd", ["Wind 6", "Solar 40"])
w("generator_fuelcost2050.dd", ["Gas 70", "Nuclear 6", "pgen 0"])
w("generator_capacities.dd", ["Wind 0", "Solar 0", "Gas 0", "Nuclear 0", "pgen 0"])
w("generator_min_gen.dd", ["Gas 0", "Nuclear 0", "pgen 0"])
w("generator_emission_factor.dd", ["Gas 0.37", "Nuclear 0", "pgen 0"])
w("generator_max_ramp.dd", ["Gas 1", "Nuclear 1", "pgen 1"])
# annualised capital cost per MW (EUR/MW/yr, assumed) scaled to the week
ann = {"Wind": 95000, "Solar": 45000, "Gas": 48000, "Nuclear": 280000}
w("generator_capex2050.dd", [f"{g} {ann[g] * WEEK:.2f}" for g in ann] + ["pgen 0"])
w("generator_varom.dd", ["Wind 3", "Solar 1", "Gas 4", "Nuclear 8", "pgen 0"])
w("generator_avail_factor.dd", ["Gas 0.95", "Nuclear 0.9", "pgen 1"])
w("transmission_loss.dd", ["HVAC 0.01"])
w("transmission_varom.dd", ["HVAC 0"])
w("transmission_capex.dd", [f"HVAC {900 * WEEK:.2f}"])
# storage: battery (4 h) and hydrogen (assumed)
w("storage_all.dd", ["Battery"])
w("storage_capacities.dd", ["Battery 0"])
w("storage_gen_capex2050.dd", [f"Battery {38000 * WEEK:.2f}"])
w("storage_cap_capex2050.dd", [f"Battery {9000 * WEEK:.2f}"])
w("storage_varom.dd", ["Battery 1"])
w("storage_loss.dd", ["Battery 0.05"])
w("storage_loss_per_hour.dd", ["Battery 0.0001"])
w("storage_gen_to_cap.dd", ["Battery 4"])
# demand (MW) and VRE capacity factors by region and hour
w("x_annual_demand_x.dd", [f"{z}.{i + 1} {load[z].iloc[i]:.1f}" for z in ZONES for i in range(H)])
w("vre_x_agg_x.dd", [f"{g}.{z}.{i + 1} {df[z].iloc[i]:.4f}" for g, df in (("Wind", wind), ("Solar", pv)) for z in ZONES for i in range(H)])
print(label, start, "demand mean MW", load.mean().round(0).to_dict(), "wind CF", wind.mean().round(3).to_dict(), "pv CF", pv.mean().round(3).to_dict())
