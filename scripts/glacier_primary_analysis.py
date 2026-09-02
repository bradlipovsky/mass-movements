#!/usr/bin/env python3
"""Stage exact participant requests, background features, and primary contrasts."""
import argparse, calendar, csv, hashlib, importlib.metadata, json, math, os, platform, shutil, subprocess, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "data/glacier_warming_steepness"
PROGRAM = Path(__file__).resolve(); TESTS = ROOT / "tests/test_glacier_primary_analysis.py"
SCHEMA = ROOT / "protocol/glacier_primary_output_schemas.json"; REQS = ROOT / "requirements-glacier-primary.txt"
SNAPSHOT = "T9H8SG2PVXWNY0QNJPJG"; SPATIAL_SHA = "8bacc9792e40926fd579e4e26ccb9c0f688683ca2796300d4e0253759ccc19ae"
PINS = {"spatial_freeze_manifest.json": SPATIAL_SHA,
 "glacier_era5_weights.csv": "baeee795dfcd79b1e67eee9337f192c897f8d4ea10ed37fd0174410544e6ec9a",
 "frame_manifest.json": "f642c90727995b64328d333a17942ce051eb18040cba3851d48dfb0905fc2254",
 "../geographic_sample/source_manifest.json": "6b411fc26af146c9dd0959490775e413aa97f57491cf6de6c91261e7e09e196b"}
STAGES={"primary_plan":("value-free participant access plan; outcomes unopened",{"primary_access_requests.csv"}),
 "primary_background":("label-free participant RGI slope and antecedent ERA5 background",{"rgi_surface_features.csv","era5_cell_year.csv","era5_access_ledger.csv","glacier_year_t2m.csv","background_features.csv"}),
 "results":("primary descriptive matched contrasts",{"primary_features.csv","case_completeness.csv","matched_contrasts.csv","dependence_ledger.csv","cluster_contrasts.csv","decision.csv"})}

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()
def rows(path):
    with open(path,newline="") as f: return list(csv.DictReader(f))
def git(*args): return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()
def write_csv(path, fields, values):
    with open(path,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader(); w.writerows(values)
def median(values):
    s=sorted(values); n=len(s); return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
def schema(): return json.loads(SCHEMA.read_text())["artifacts"]
def fields(name): return [column[0] for column in schema()[name]["columns"]]
def environment():
    expected={"icechunk":"2.1.2","numpy":"2.5.2","pcodec":"1.0.3","xarray":"2026.7.0"}
    actual={name:importlib.metadata.version(name) for name in expected}
    if actual!=expected: raise ValueError("approved package environment drift")
    return {"python":platform.python_version(),"platform":platform.platform(),"packages":actual}
def validate_table(name,data):
    spec=schema()[name]; columns=spec["columns"]
    if any(set(r)!=set(fields(name)) for r in data): raise ValueError(f"{name} column drift")
    if len({tuple(str(r[k]) for k in spec["key"]) for r in data})!=len(data): raise ValueError(f"{name} duplicate key")
    for row in data:
        for key,kind,_,nullable in columns:
            value=row[key]
            if value in ("",None):
                if not nullable: raise ValueError(f"{name} null in {key}")
            elif kind=="float64" and not math.isfinite(float(value)): raise ValueError(f"{name} nonfinite {key}")
            elif kind=="integer": int(value)
            elif kind=="boolean" and str(value) not in ("True","False"): raise ValueError(f"{name} invalid boolean")
    if any(r.get("endpoint","") not in ("","t2m_trend_k_decade","slope_deg") for r in data): raise ValueError("endpoint enum drift")
def preflight(stage):
    targets=[OUT/name for name in STAGES[stage][1]]+[OUT/f"{stage}_manifest.json"]
    if any(path.exists() for path in targets): raise FileExistsError("refusing to replace staged output")
    if git("status","--porcelain"): raise ValueError("stage requires clean worktree")
def checked_inputs():
    paths={"spatial_freeze_manifest.json":OUT/"spatial_freeze_manifest.json",
           "glacier_era5_weights.csv":OUT/"glacier_era5_weights.csv",
           "frame_manifest.json":OUT/"frame_manifest.json",
           "../geographic_sample/source_manifest.json":ROOT/"data/geographic_sample/source_manifest.json"}
    for name,path in paths.items():
        if sha(path)!=PINS[name]: raise ValueError(f"frozen input drift: {name}")
    spatial=json.loads(paths["spatial_freeze_manifest.json"].read_text())
    if (spatial["rgi_ids"],spatial["weight_rows"],spatial["unique_era5_cells"],spatial["final_clusters"])!=(207,235,133,5):
        raise ValueError("spatial counts drift")
    for name in ("case_frame.csv","case_glacier_status.csv","selected_backgrounds.csv"):
        rec=spatial["inputs"][f"data/glacier_warming_steepness/{name}"]; path=OUT/name
        if path.stat().st_size!=rec["bytes"] or sha(path)!=rec["sha256"]: raise ValueError(f"spatial input replay failed: {name}")
    for name in ("glacier_era5_weights.csv","spatial_dependence_ledger.csv"):
        rec=spatial["outputs"][name]; path=OUT/name
        if path.stat().st_size!=rec["bytes"] or sha(path)!=rec["sha256"]: raise ValueError(f"spatial output replay failed: {name}")
    for name in ("protocol/global-glacier-warming-steepness.md","protocol/glacier_warming_steepness_output_schemas.json"):
        rec=spatial["inputs"][name]; path=ROOT/name
        if path.stat().st_size!=rec["bytes"] or sha(path)!=rec["sha256"]: raise ValueError(f"governing protocol drift: {name}")
    return paths
def approved_code(commit):
    names=[str(p.relative_to(ROOT)) for p in (PROGRAM,TESTS,SCHEMA,REQS)]
    if subprocess.call(["git","diff","--quiet",commit,"--",*names],cwd=ROOT): raise ValueError("approved program files drift")
def verify_stage(stage,approved_sha):
    path=OUT/f"{stage}_manifest.json"
    if sha(path)!=approved_sha: raise ValueError(f"unapproved {stage} manifest")
    manifest=json.loads(path.read_text()); status,names=STAGES[stage]
    if manifest.get("status")!=status or set(manifest.get("outputs",{}))!=names: raise ValueError(f"{stage} manifest contract drift")
    tables={}
    for name,rec in manifest["outputs"].items():
        target=OUT/name
        data=rows(target); tables[name]=data; spec=schema()[name]; validate_table(name,data)
        if (target.stat().st_size!=rec["bytes"] or sha(target)!=rec["sha256"] or len(data)!=rec["rows"]
                or list(data[0])!=fields(name) or len({tuple(r[k] for k in spec["key"]) for r in data})!=len(data)):
            raise ValueError(f"{stage} output replay failed: {name}")
    if stage=="primary_plan" and (len(tables["primary_access_requests.csv"])!=manifest["requests"] or manifest["rgi_ids"]!=207): raise ValueError("plan cardinality drift")
    if stage=="primary_background" and (len(tables["rgi_surface_features.csv"])!=207 or len(tables["era5_cell_year.csv"])!=manifest["cell_years"]): raise ValueError("background cardinality drift")
    if stage=="results" and tuple(len(tables[x]) for x in ("primary_features.csv","case_completeness.csv","matched_contrasts.csv","dependence_ledger.csv","decision.csv"))!=(210,420,20,10,1): raise ValueError("result cardinality drift")
    return manifest
def participants():
    cases={r["candidate_id"]:r for r in rows(OUT/"case_frame.csv") if r["primary_case"]=="True"}
    status={r["candidate_id"]:r for r in rows(OUT/"case_glacier_status.csv")}
    controls={c:[] for c in cases}
    for r in rows(OUT/"selected_backgrounds.csv"):
        if r["selected"]=="True": controls[r["candidate_id"]].append(r["rgi_id"])
    if len(cases)!=10 or any(len(v)!=20 for v in controls.values()): raise ValueError("participant frame drift")
    rel=[]
    for c in sorted(cases):
        y=int(cases[c]["index_year"]); rel.append((c,"case",status[c]["rgi_id"],y))
        rel += [(c,"control",r,y) for r in controls[c]]
    if len(rel)!=210 or len({x[2] for x in rel})!=207: raise ValueError("participant identities drift")
    return rel
def publish(stage, outputs, manifest, fail_after=None):
    targets=[OUT/name for name in outputs]+[OUT/f"{stage}_manifest.json"]
    if any(p.exists() for p in targets) or set(outputs)!=STAGES[stage][1]: raise FileExistsError("invalid or existing staged output")
    tmp=Path(tempfile.mkdtemp(prefix=f".{stage}-",dir=OUT)); linked=[]
    try:
        for name,(columns,data) in outputs.items(): validate_table(name,data); write_csv(tmp/name,columns,data)
        manifest["outputs"]={name:{"rows":len(data),"bytes":(tmp/name).stat().st_size,"sha256":sha(tmp/name)} for name,(_,data) in outputs.items()}
        if stage=="results": manifest["output_sha256"]={name:record["sha256"] for name,record in manifest["outputs"].items()}
        (tmp/f"{stage}_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        for i,name in enumerate([*outputs,f"{stage}_manifest.json"]):
            os.link(tmp/name,OUT/name); linked.append(OUT/name)
            if fail_after==i+1: raise RuntimeError("injected publication failure")
    except Exception:
        for p in linked: p.unlink(missing_ok=True)
        raise
    finally: shutil.rmtree(tmp,ignore_errors=True)

def make_plan(approved_commit):
    checked_inputs()
    if git("rev-parse","HEAD")!=approved_commit or git("status","--porcelain"): raise ValueError("plan requires approved clean HEAD")
    preflight("primary_plan")
    weights=rows(OUT/"glacier_era5_weights.csv"); by={}
    for r in weights: by.setdefault(r["rgi_id"],[]).append(r)
    requests=set()
    for _,_,rgi,y in participants():
        if rgi not in by: raise ValueError("participant lacks frozen support")
        for year in range(y-20,y):
            if year<1981 or year>2022: raise ValueError("year outside registered access")
            for w in by[rgi]: requests.add((rgi,y,year,w["latitude"],w["longitude"]))
    data=[dict(zip(("rgi_id","index_year","year","latitude","longitude"),r)) for r in sorted(requests)]
    manifest={"status":"value-free participant access plan; outcomes unopened","git_commit":approved_commit,
      "spatial_manifest_sha256":SPATIAL_SHA,"requests":len(data),"rgi_ids":len({r[0] for r in requests}),
      "cell_years":len({r[2:] for r in requests}),"created_at":datetime.now(timezone.utc).isoformat()}
    publish("primary_plan",{"primary_access_requests.csv":(fields("primary_access_requests.csv"),data)},manifest)

def rgi_features(wanted):
    source=json.loads((ROOT/"data/geographic_sample/source_manifest.json").read_text()); frame_meta=json.loads((OUT/"frame_manifest.json").read_text()); found={}
    frame={}
    for region in ("01","13","17"):
        frame_path=OUT/f"rgi_matching_frame/{region}.csv"; rec_frame=frame_meta["files"][f"{region}.csv"]
        if frame_path.stat().st_size!=rec_frame["bytes"] or sha(frame_path)!=rec_frame["sha256"]: raise ValueError("RGI frame partition drift")
        for r in rows(frame_path):
            if r["rgi_id"] in wanted: frame[r["rgi_id"]]=r
        rec=next(r for r in source["archives"] if r["region"]==region)
        archive=ROOT/"data/geographic_sample/source_raw/rgi"/rec["filename"]
        if archive.stat().st_size!=rec["bytes"] or sha(archive)!=rec["sha256"]: raise ValueError("RGI archive drift")
        member=next(m["name"] for m in rec["members"] if m["name"].endswith("-attributes.csv") and "/" not in m["name"])
        import io
        with zipfile.ZipFile(archive) as z, z.open(member) as raw:
            for r in csv.DictReader(io.TextIOWrapper(raw,encoding="utf-8-sig",newline="")):
                if r["rgi_id"] not in wanted: continue
                if r["rgi_id"] in found: raise ValueError("duplicate RGI outcome")
                try: value=float(r["slope_deg"]); ok=math.isfinite(value) and 0<=value<=90
                except ValueError: ok=False
                f=frame[r["rgi_id"]]; found[r["rgi_id"]]={"rgi_id":r["rgi_id"],"slope_deg":f"{value:.17g}" if ok else "",
                  "dem_source":f["dem_source"],"rgi_grid_spacing_m":f["rgi_grid_spacing_m"],"src_date":f["src_date"],
                  "missing_reason":"" if ok else "slope:missing_or_invalid"}
    if set(found)!=wanted or set(frame)!=wanted: raise ValueError("RGI participant outcome missing")
    return [found[k] for k in sorted(found)]

def glacier_years(requests,weight_rows,cell_years):
    weights={}
    for r in weight_rows: weights.setdefault(r["rgi_id"],{})[(r["latitude"],r["longitude"])]=float(r["weight"])
    era={(r["latitude"],r["longitude"],int(r["year"])):r for r in cell_years}; keys={(r["rgi_id"],int(r["index_year"]),int(r["year"])) for r in requests}; out=[]
    for rgi,index_year,year in sorted(keys):
        requested={(r["latitude"],r["longitude"]) for r in requests if r["rgi_id"]==rgi and int(r["index_year"])==index_year and int(r["year"])==year}
        if requested!=set(weights[rgi]): raise ValueError("request does not conserve frozen support")
        total=math.fsum(weights[rgi].values()); missing=[]; terms=[]
        for (lat,lon),weight in weights[rgi].items():
            row=era[(lat,lon,year)]
            if not row["t2m_mean_k"]: missing.append(f"{lat},{lon},{year}")
            else: terms.append(weight*float(row["t2m_mean_k"]))
        out.append({"rgi_id":rgi,"index_year":index_year,"year":year,"t2m_mean_k":"" if missing else f"{math.fsum(terms):.17g}",
                    "weight_sum":f"{total:.17g}","missing_reason":f"t2m:missing_cell_year:{'|'.join(missing)}" if missing else ""})
        if abs(total-1)>1e-12: raise ValueError("frozen weight sum drift")
    return out

def background_features(requests,slopes,glacier_rows):
    slope={r["rgi_id"]:r for r in slopes}; annual={(r["rgi_id"],int(r["index_year"]),int(r["year"])):r for r in glacier_rows}
    pairs=sorted({(r["rgi_id"],int(r["index_year"])) for r in requests}); out=[]
    for rgi,index_year in pairs:
        yearly=[annual[(rgi,index_year,y)] for y in range(index_year-20,index_year)]; miss=[]
        if any(not r["t2m_mean_k"] for r in yearly): miss.append("t2m:incomplete_20_year_window")
        if not slope[rgi]["slope_deg"]: miss.append(slope[rgi]["missing_reason"])
        values=("","","","") if miss and any(x.startswith("t2m:") for x in miss) else tuple(f"{v:.17g}" for v in trend([float(r["t2m_mean_k"]) for r in yearly]))
        out.append(dict(zip(fields("background_features.csv"),[rgi,index_year,*values,slope[rgi]["slope_deg"],";".join(miss)])))
    return out
def calendar_slice(times,year):
    import numpy as np
    expected=np.arange(np.datetime64(f"{year}-01-01T00"),np.datetime64(f"{year+1}-01-01T00"),np.timedelta64(1,"h"))
    start=int(np.searchsorted(times,expected[0],side="left")); stop=int(np.searchsorted(times,expected[-1]+np.timedelta64(1,"h"),side="left"))
    actual=times[start:stop]; exact=expected.astype(actual.dtype)
    if len(expected)!=(8784 if calendar.isleap(year) else 8760) or len(actual)!=len(expected) or not np.array_equal(actual,exact):
        raise ValueError("missing, duplicate, or unordered ERA5 hour")
    return start,len(expected)
def coordinate_index(values,requested):
    lookup={float(value):index for index,value in enumerate(values)}; target=float(requested)
    if len(lookup)!=len(values) or target not in lookup or float(values[lookup[target]])!=target: raise ValueError("ERA5 coordinate mismatch")
    return lookup[target]

def era_features(request_keys):
    import icechunk, numpy as np, pcodec, xarray as xr  # noqa: F401
    storage=icechunk.s3_storage(bucket="earthmover-icechunk-era5",prefix="icechunkV2",region="us-east-1",anonymous=True)
    session=icechunk.Repository.open(storage).readonly_session(snapshot_id=SNAPSHOT)
    ds=xr.open_zarr(session.store,group="single/temporal",consolidated=False,chunks=None); var=ds.t2m
    if tuple(var.dims)!=("valid_time","latitude","longitude") or var.attrs.get("units")!="K": raise ValueError("ERA5 variable identity drift")
    lats=np.asarray(ds.latitude.values); lons=np.asarray(ds.longitude.values); times=np.asarray(ds.valid_time.values)
    chunks=var.encoding.get("chunks")
    if not chunks or len(chunks)!=3 or not all(isinstance(v,int) and v>0 for v in chunks): raise ValueError("ERA5 chunk metadata unavailable")
    lat_chunk,lon_chunk=chunks[1:]
    cells_by_year={}
    for lat,lon,year in request_keys:
        flat,flon=float(lat),float(lon)
        cells_by_year.setdefault(year,[]).append((lat,lon,coordinate_index(lats,flat),coordinate_index(lons,flon)))
    out=[]; access=[]
    for year in sorted(cells_by_year):
        start,hours=calendar_slice(times,year)
        tiles={}
        for c in sorted(set(cells_by_year[year])): tiles.setdefault((c[2]//lat_chunk,c[3]//lon_chunk),[]).append(c)
        for tile,cells in sorted(tiles.items()):
            ai=np.array([c[2] for c in cells]); aj=np.array([c[3] for c in cells])
            block=np.asarray(var.isel(valid_time=slice(start,start+hours),latitude=xr.DataArray(ai,dims="point"),longitude=xr.DataArray(aj,dims="point")).values)
            if block.shape!=(hours,len(cells)): raise ValueError("invalid ERA5 payload shape")
            access.append({"year":year,"latitude_tile":tile[0],"longitude_tile":tile[1],"points":len(cells),"hours":hours})
            for p,(lat,lon,_,_) in enumerate(cells):
                values=block[:,p]; ok=bool(np.isfinite(values).all()); mean=math.fsum(float(v) for v in values)/hours if ok else None
                out.append({"latitude":lat,"longitude":lon,"year":year,"hour_count":hours,"t2m_mean_k":f"{mean:.17g}" if ok else "",
                            "missing_reason":"" if ok else "t2m:nonfinite_cell_year"})
        print(f"ERA5 {year}: {len(cells_by_year[year])} cells")
    return sorted(out,key=lambda r:(int(r["year"]),float(r["latitude"]),float(r["longitude"]))),access

def extract_background(approved_commit,approved_plan_sha):
    checked_inputs(); plan=OUT/"primary_plan_manifest.json"; plan_meta=verify_stage("primary_plan",approved_plan_sha)
    if plan_meta["git_commit"]!=approved_commit: raise ValueError("plan and program commits differ")
    if subprocess.call(["git","merge-base","--is-ancestor",approved_commit,"HEAD"],cwd=ROOT): raise ValueError("unapproved program commit")
    approved_code(approved_commit)
    preflight("primary_background"); env=environment()
    req=rows(OUT/"primary_access_requests.csv"); wanted={r["rgi_id"] for r in req}
    keys={(r["latitude"],r["longitude"],int(r["year"])) for r in req}
    slopes=rgi_features(wanted); era,access=era_features(keys); glacier=glacier_years(req,rows(OUT/"glacier_era5_weights.csv"),era); features=background_features(req,slopes,glacier)
    used=[PROGRAM,TESTS,SCHEMA,REQS,plan,OUT/"primary_access_requests.csv",OUT/"spatial_freeze_manifest.json",OUT/"glacier_era5_weights.csv",
          OUT/"frame_manifest.json",ROOT/"data/geographic_sample/source_manifest.json",ROOT/"protocol/global-glacier-warming-steepness.md",
          ROOT/"protocol/glacier_warming_steepness_output_schemas.json"]
    source=json.loads((ROOT/"data/geographic_sample/source_manifest.json").read_text())
    for region in ("01","13","17"):
        used.append(OUT/f"rgi_matching_frame/{region}.csv")
        used.append(ROOT/"data/geographic_sample/source_raw/rgi"/next(r["filename"] for r in source["archives"] if r["region"]==region))
    manifest={"status":STAGES["primary_background"][0],"git_commit":git("rev-parse","HEAD"),
      "approved_program_commit":approved_commit,"approved_plan_sha256":approved_plan_sha,"snapshot":SNAPSHOT,
      "rgi_ids":len(wanted),"cell_years":len(keys),"created_at":datetime.now(timezone.utc).isoformat(),
      "source_identity":{"era5":{"bucket":"earthmover-icechunk-era5","prefix":"icechunkV2","group":"single/temporal","variable":"t2m","snapshot":SNAPSHOT},"rgi_doi":"10.5067/F6JMOVY5NAVZ"},
      "environment":env,
      "inputs":{str(p.relative_to(ROOT)):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in used}}
    publish("primary_background",{"rgi_surface_features.csv":(fields("rgi_surface_features.csv"),slopes),
      "era5_cell_year.csv":(fields("era5_cell_year.csv"),era),"era5_access_ledger.csv":(fields("era5_access_ledger.csv"),access),
      "glacier_year_t2m.csv":(fields("glacier_year_t2m.csv"),glacier),"background_features.csv":(fields("background_features.csv"),features)},manifest)

def trend(values):
    if len(values)!=20 or not all(math.isfinite(v) for v in values): raise ValueError("trend requires 20 finite years")
    mean=math.fsum(values)/20; beta=math.fsum((i-9.5)*v for i,v in enumerate(values))/665; a=mean-9.5*beta
    e=[v-a-beta*i for i,v in enumerate(values)]; S=[[0.,0.],[0.,0.]]
    for lag,w in ((0,1.),(1,2/3),(2,1/3)):
        for t in range(lag,20):
            u=e[t]*e[t-lag]; xt=(1.,t); xl=(1.,t-lag)
            for i in range(2):
                for j in range(2): S[i][j]+=u*xt[i]*xl[j]*(1 if lag==0 else w)+ (0 if lag==0 else u*xl[i]*xt[j]*w)
    inv=((2470/13300,-190/13300),(-190/13300,20/13300)); v11=0.
    for i in range(2):
        for j in range(2): v11+=inv[1][i]*S[i][j]*inv[j][1]
    slopes=[(values[j]-values[i])/(j-i) for i in range(20) for j in range(i+1,20)]
    variance=v11*20/18; scale=max(1.,max(abs(v) for v in values)**2)
    if variance < -1e-14*scale: raise ValueError("materially negative HAC variance")
    return 10*beta,19*beta,10*math.sqrt(max(0.,variance)),10*median(slopes)
def sign_stats(values):
    if not values: return 0,1,"","","",""
    n=len(values); k=sum(v>0 for v in values); p=sum(math.comb(n,j) for j in range(k,n+1))/2**n
    valid=[r for r in range(1,n+1) if 2*sum(math.comb(n,j) for j in range(r))/2**n<=.05]
    s=sorted(values); lo=hi=""
    if valid: r=max(valid); lo=f"{s[r-1]:.17g}"; hi=f"{s[n-r]:.17g}"
    walsh=[(values[i]+values[j])/2 for i in range(n) for j in range(i,n)]
    return k,p,median(values),lo,hi,median(walsh)
def decision(gate,w,s,a):
    if not gate: return "INDETERMINATE",None
    if w>0 and s>0 and a>0: return "DESCRIPTIVE_ONLY","consistent"
    if w<=0 and s<=0: return "DESCRIPTIVE_ONLY","inconsistent"
    return "DESCRIPTIVE_ONLY","mixed"

def matched_value(case_value,controls):
    if case_value in (None,"") or len(controls)!=20 or any(v in (None,"") for v in controls): return None
    case_value=float(case_value); values=[float(v) for v in controls]; med=median(values); all_values=values+[case_value]
    return med,case_value-med,100*(sum(v<case_value for v in all_values)+.5*sum(v==case_value for v in all_values))/21

def build_analysis(rel,background,spatial):
    by={(r["rgi_id"],int(r["index_year"])):r for r in background}; features=[]
    for case,role,rgi,index_year in rel:
        b=by[(rgi,index_year)]; features.append(dict(zip(fields("primary_features.csv"),[case,role,rgi,index_year,b["t2m_trend_k_decade"],
          b["t2m_change_k"],b["t2m_hac_se_k_decade"],b["slope_deg"],b["missing_reason"]])))
    completeness=[]
    for f in features:
        for endpoint,key,prefix in (("t2m_trend_k_decade","t2m_trend_k_decade","t2m:"),("slope_deg","slope_deg","slope:")):
            reason=next((x for x in f["missing_reason"].split(";") if x.startswith(prefix)),"")
            completeness.append(dict(zip(fields("case_completeness.csv"),[f["candidate_id"],f["rgi_id"],f["role"],endpoint,bool(f[key]),reason])))
    final={r["candidate_id"]:r for r in spatial}; endpoint_ok={}; direct={}
    for case in sorted(final):
        group=[r for r in completeness if r["candidate_id"]==case]
        endpoint_ok[case]={e:all(r["complete"] for r in group if r["endpoint"]==e) for e in ("t2m_trend_k_decade","slope_deg")}
        direct[case]=all(endpoint_ok[case].values())
    clusters={r["final_cluster"]:{x for x in final if final[x]["final_cluster"]==r["final_cluster"]} for r in spatial}
    retained={cluster for cluster,cases in clusters.items() if all(direct[c] for c in cases)}
    causes={cluster:"|".join(f"{r['candidate_id']}:{r['endpoint']}:{r['rgi_id']}" for r in completeness
              if r["candidate_id"] in cases and not r["complete"]) for cluster,cases in clusters.items()}
    contrasts=[]
    for case in sorted(final):
        group=[f for f in features if f["candidate_id"]==case]; case_row=next(f for f in group if f["role"]=="case")
        for endpoint in ("t2m_trend_k_decade","slope_deg"):
            result=matched_value(case_row[endpoint],[f[endpoint] for f in group if f["role"]=="control"])
            if final[case]["final_cluster"] not in retained:
                record=[case,final[case]["final_cluster"],endpoint,case_row[endpoint],"","","",f"component_excluded_by:{causes[final[case]['final_cluster']]}"]
            elif result is None: raise ValueError("retained component lacks complete endpoint")
            else: record=[case,final[case]["final_cluster"],endpoint,case_row[endpoint],*result,""]
            contrasts.append(dict(zip(fields("matched_contrasts.csv"),record)))
    dep=[]
    for case in sorted(final):
        cluster=final[case]["final_cluster"]; dep.append(dict(zip(fields("dependence_ledger.csv"),[case,final[case]["initial_cluster"],cluster,direct[case],
          cluster in retained,"" if cluster in retained else f"component_excluded_by:{causes[cluster]}"])))
    cc=[]
    for cluster in sorted(retained):
        for endpoint in ("t2m_trend_k_decade","slope_deg"):
            values=[float(r["contrast"]) for r in contrasts if r["final_cluster"]==cluster and r["endpoint"]==endpoint]
            contrast=math.fsum(values)/len(values); cc.append(dict(zip(fields("cluster_contrasts.csv"),[cluster,endpoint,len(values),contrast,contrast>0])))
    stats={}
    for endpoint in ("t2m_trend_k_decade","slope_deg"):
        stats[endpoint]=sign_stats([float(r["contrast"]) for r in cc if r["endpoint"]==endpoint])
    raw=[]
    for cluster in sorted(retained):
        values=[float(f["t2m_trend_k_decade"]) for f in features if f["role"]=="case" and final[f["candidate_id"]]["final_cluster"]==cluster]
        raw.append(math.fsum(values)/len(values))
    absolute=median(raw) if raw else ""; cases=sum(len(clusters[c]) for c in retained); warming=stats["t2m_trend_k_decade"]; slope=stats["slope_deg"]
    common={r["final_cluster"] for r in cc if r["endpoint"]=="t2m_trend_k_decade"}=={r["final_cluster"] for r in cc if r["endpoint"]=="slope_deg"}
    status,direction=decision(cases>=8 and common,warming[2],slope[2],absolute)
    reason="Documented cases versus matched RGI comparison objects, which are not verified nonfailures. Strictly antecedent ERA5 2-m air temperature is at model orography; RGI slope is a mixed-epoch glacier-wide mean attribute. Neither is pre-event source geometry, a causal warming-trigger mechanism, failure probability, or risk."
    decision_row=dict(zip(fields("decision.csv"),["glacier_warming_steepness",status,direction or "",cases,len(retained),warming[0],slope[0],warming[2],warming[3],warming[4],warming[5],
      slope[2],slope[3],slope[4],slope[5],absolute,warming[1],slope[1],max(warming[1],slope[1]),reason]))
    return {"primary_features.csv":features,"case_completeness.csv":completeness,"matched_contrasts.csv":contrasts,
            "dependence_ledger.csv":dep,"cluster_contrasts.csv":cc,"decision.csv":[decision_row]}

def analyze(approved_background_sha):
    bg_meta=verify_stage("primary_background",approved_background_sha); checked_inputs()
    approved_code(bg_meta["approved_program_commit"])
    preflight("results"); data=build_analysis(participants(),rows(OUT/"background_features.csv"),rows(OUT/"spatial_dependence_ledger.csv"))
    outputs={name:(fields(name),values) for name,values in data.items()}; protocol_commit=git("log","-1","--format=%H","--","protocol/global-glacier-warming-steepness.md")
    manifest={"status":STAGES["results"][0],"protocol_commit":protocol_commit,"program_sha256":sha(PROGRAM),"schema_sha256":sha(SCHEMA),
      "environment":environment(),"source_identity":bg_meta["source_identity"],
      "access_audit":{"approved_background_sha256":approved_background_sha,"approved_program_commit":bg_meta["approved_program_commit"]},"created_at":datetime.now(timezone.utc).isoformat()}
    publish("results",outputs,manifest)

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="stage",required=True)
    a=sub.add_parser("plan"); a.add_argument("--approved-program-commit",required=True)
    b=sub.add_parser("background"); b.add_argument("--approved-program-commit",required=True); b.add_argument("--approved-plan-sha",required=True)
    c=sub.add_parser("analyze"); c.add_argument("--approved-background-sha",required=True)
    x=p.parse_args()
    if x.stage=="plan": make_plan(x.approved_program_commit)
    elif x.stage=="background": extract_background(x.approved_program_commit,x.approved_plan_sha)
    else: analyze(x.approved_background_sha)
if __name__=="__main__": main()
