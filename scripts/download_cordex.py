"""Select and download four EURO-CORDEX daily sfcWind files (DKRZ ESGF node): CNRM-CM5 driving CLMcom-ETH-COSMO-crCLIM-v1-1,
historical 1996-2005 and RCP8.5 2091-2100 (about 4.5 GB)."""
import requests, json
base="https://esgf-data.dkrz.de/esg-search/search"
out=[]
for ex,pers in (("historical",("19960101","20010101")),("rcp85",("20910101","20960101"))):
    d=requests.get(base,params=dict(project="CORDEX",domain="EUR-11",type="File",variable="sfcWind",time_frequency="day",experiment=ex,limit=400,format="application/solr+json",distrib="false"),timeout=120).json()["response"]["docs"]
    for x in d:
        if "CNRM-CM5" in x["title"] and "CLMcom-ETH" in x["title"] and any(("_day_"+p) in x["title"] for p in pers):
            u=[a.split("|")[0] for a in x["url"] if a.endswith("HTTPServer")][0].replace("http://","https://")
            out.append((x["title"],u,x["size"])); print(x["title"],x["size"]/1e6)
import os
from pathlib import Path
dest = Path(os.environ.get("CORDEX_DIR", Path.home() / "z_data" / "z6_cordex" / "nc")); dest.mkdir(parents=True, exist_ok=True)
# the files are about 1.1 GB each; curl with resume (-C -) because the node is slow
for title, u, size in out:
    os.system(f'curl -sL -C - --retry 20 --retry-delay 10 -o "{dest / title}" "{u}"')
