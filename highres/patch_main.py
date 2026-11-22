"""Patch a copy of highRES.gms for the small instance: file-name switches, HiGHS instead of CPLEX, no SQL export."""
import re
import sys
from pathlib import Path

d = sys.argv[1]
p = f"{d}/highRES.gms"
s = open(p).read()
for k, v in (("uktm_scen", "x"), ("area_scen", "x"), ("nuc_restrict", "x"), ("year", "x"), ("RPS_scen", "0"),
             ("gdx2sql", "OFF"), ("outname", "hR_" + Path(d).name)):
    s = re.sub(r"\$setglobal " + k + r" .*", lambda m: '$setglobal ' + k + ' "' + v + '"', s)
s = s.replace("Option LP = CPLEX;", "Option LP = HIGHS;").replace("Dispatch.OptFile = 1;", "")
s = re.sub(r"\$onecho > cplex\.opt.*?\$offecho", "", s, flags=re.S)
s = s.replace("=L= 4.4", "=L= 50")  # carbon intensity limit in kg/MWh (g/kWh); the original 4.4 is a UK 2050 value
open(p, "w").write(s)
print("patched", p)
