#!/usr/bin/env python3
"""Stage exact participant requests, background features, and primary contrasts."""
import argparse, calendar, csv, hashlib, json, math, os, platform, shutil, subprocess, tempfile, zipfile
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
    return paths
def approved_code(commit):
    names=[str(p.relative_to(ROOT)) for p in (PROGRAM,TESTS,SCHEMA,REQS)]
    if subprocess.call(["git","diff","--quiet",commit,"--",*names],cwd=ROOT): raise ValueError("approved program files drift")
def verify_stage(stage,approved_sha):
    path=OUT/f"{stage}_manifest.json"
    if sha(path)!=approved_sha: raise ValueError(f"unapproved {stage} manifest")
    manifest=json.loads(path.read_text())
    for name,rec in manifest["outputs"].items():
        target=OUT/name
        if target.stat().st_size!=rec["bytes"] or sha(target)!=rec["sha256"] or len(rows(target))!=rec["rows"]:
            raise ValueError(f"{stage} output replay failed: {name}")
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
    if any(p.exists() for p in targets): raise FileExistsError("refusing to replace staged output")
    tmp=Path(tempfile.mkdtemp(prefix=f".{stage}-",dir=OUT)); linked=[]
    try:
        for name,(fields,data) in outputs.items(): write_csv(tmp/name,fields,data)
        manifest["outputs"]={name:{"rows":len(data),"bytes":(tmp/name).stat().st_size,"sha256":sha(tmp/name)} for name,(_,data) in outputs.items()}
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
    publish("primary_plan",{"primary_access_requests.csv":(json.loads(SCHEMA.read_text())["primary_access_requests.csv"],data)},manifest)

def rgi_features(wanted):
    source=json.loads((ROOT/"data/geographic_sample/source_manifest.json").read_text()); found={}
    frame={}
    for region in ("01","13","17"):
        for r in rows(OUT/f"rgi_matching_frame/{region}.csv"):
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
                  "src_date":f["src_date"],"dem_source":f["dem_source"],"rgi_grid_spacing_m":f["rgi_grid_spacing_m"],
                  "missing_reason":"" if ok else "slope:missing_or_invalid"}
    if set(found)!=wanted or set(frame)!=wanted: raise ValueError("RGI participant outcome missing")
    return [found[k] for k in sorted(found)]
def calendar_slice(times,year):
    import numpy as np
    expected=np.arange(np.datetime64(f"{year}-01-01T00"),np.datetime64(f"{year+1}-01-01T00"),np.timedelta64(1,"h"))
    start=int(np.searchsorted(times,expected[0])); actual=times[start:start+len(expected)].astype("datetime64[h]")
    if len(expected)!=(8784 if calendar.isleap(year) else 8760) or not np.array_equal(actual,expected):
        raise ValueError("missing, duplicate, or unordered ERA5 hour")
    return start,len(expected)

def era_features(request_keys):
    import icechunk, numpy as np, pcodec, xarray as xr  # noqa: F401
    storage=icechunk.s3_storage(bucket="earthmover-icechunk-era5",prefix="icechunkV2",region="us-east-1",anonymous=True)
    session=icechunk.Repository.open(storage).readonly_session(snapshot_id=SNAPSHOT)
    ds=xr.open_zarr(session.store,group="single/temporal",consolidated=False,chunks=None); var=ds.t2m
    if tuple(var.dims)!=("valid_time","latitude","longitude") or var.attrs.get("units")!="K": raise ValueError("ERA5 variable identity drift")
    lats=np.asarray(ds.latitude.values); lons=np.asarray(ds.longitude.values); times=np.asarray(ds.valid_time.values)
    li={f"{float(v):.2f}":i for i,v in enumerate(lats)}; lj={f"{float(v):.2f}":i for i,v in enumerate(lons)}
    cells_by_year={}
    for lat,lon,year in request_keys:
        if lat not in li or lon not in lj: raise ValueError("ERA5 coordinate mismatch")
        cells_by_year.setdefault(year,[]).append((lat,lon,li[lat],lj[lon]))
    out=[]; access=[]
    for year in sorted(cells_by_year):
        start,hours=calendar_slice(times,year)
        tiles={}
        for c in sorted(set(cells_by_year[year])): tiles.setdefault((c[2]//12,c[3]//12),[]).append(c)
        for tile,cells in sorted(tiles.items()):
            ai=np.array([c[2] for c in cells]); aj=np.array([c[3] for c in cells])
            block=np.asarray(var.isel(valid_time=slice(start,start+hours),latitude=xr.DataArray(ai,dims="point"),longitude=xr.DataArray(aj,dims="point")).values)
            if block.shape!=(hours,len(cells)) or not np.isfinite(block).all() or block.min()<180 or block.max()>340: raise ValueError("invalid ERA5 payload")
            access.append({"year":year,"latitude_tile":tile[0],"longitude_tile":tile[1],"points":len(cells),"hours":hours})
            for p,(lat,lon,_,_) in enumerate(cells):
                mean=math.fsum(float(v) for v in block[:,p])/hours
                out.append({"latitude":lat,"longitude":lon,"year":year,"hours":hours,"mean_t2m_k":f"{mean:.17g}"})
        print(f"ERA5 {year}: {len(cells_by_year[year])} cells")
    return sorted(out,key=lambda r:(int(r["year"]),float(r["latitude"]),float(r["longitude"]))),access

def extract_background(approved_commit,approved_plan_sha):
    checked_inputs(); plan=OUT/"primary_plan_manifest.json"; plan_meta=verify_stage("primary_plan",approved_plan_sha)
    if plan_meta["git_commit"]!=approved_commit: raise ValueError("plan and program commits differ")
    if subprocess.call(["git","merge-base","--is-ancestor",approved_commit,"HEAD"],cwd=ROOT): raise ValueError("unapproved program commit")
    approved_code(approved_commit)
    req=rows(OUT/"primary_access_requests.csv"); wanted={r["rgi_id"] for r in req}
    keys={(r["latitude"],r["longitude"],int(r["year"])) for r in req}
    slopes=rgi_features(wanted); era,access=era_features(keys); schemas=json.loads(SCHEMA.read_text())
    manifest={"status":"label-free participant RGI slope and antecedent ERA5 cell-year background","git_commit":git("rev-parse","HEAD"),
      "approved_program_commit":approved_commit,"approved_plan_sha256":approved_plan_sha,"snapshot":SNAPSHOT,
      "rgi_ids":len(wanted),"cell_years":len(keys),"created_at":datetime.now(timezone.utc).isoformat(),
      "inputs":{str(p.relative_to(ROOT)):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in [PROGRAM,TESTS,SCHEMA,REQS,plan,OUT/"primary_access_requests.csv"]}}
    publish("primary_background",{"rgi_surface_features.csv":(schemas["rgi_surface_features.csv"],slopes),
      "era5_cell_year.csv":(schemas["era5_cell_year.csv"],era),"era5_access_ledger.csv":(schemas["era5_access_ledger.csv"],access)},manifest)

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
    return 10*beta,19*beta,10*math.sqrt(max(0,v11*20/18)),10*median(slopes)
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

def analyze(approved_background_sha):
    bg_meta=verify_stage("primary_background",approved_background_sha); checked_inputs()
    approved_code(bg_meta["approved_program_commit"])
    rel=participants(); weights={}
    for r in rows(OUT/"glacier_era5_weights.csv"): weights.setdefault(r["rgi_id"],[]).append((r["latitude"],r["longitude"],float(r["weight"])))
    slopes={r["rgi_id"]:r for r in rows(OUT/"rgi_surface_features.csv")}; era={(r["latitude"],r["longitude"],int(r["year"])):float(r["mean_t2m_k"]) for r in rows(OUT/"era5_cell_year.csv")}
    features=[]
    for case,role,rgi,y in rel:
        miss=[]; slope=slopes[rgi]["slope_deg"]
        if not slope: miss.append(slopes[rgi]["missing_reason"])
        annual=[]
        for year in range(y-20,y):
            try:
                if abs(math.fsum(w for _,_,w in weights[rgi])-1)>1e-12: raise KeyError
                annual.append(math.fsum(w*era[(lat,lon,year)] for lat,lon,w in weights[rgi]))
            except KeyError: miss.append(f"t2m:missing_support:{year}"); break
        vals=("","","","") if len(annual)!=20 else tuple(f"{v:.17g}" for v in trend(annual))
        features.append(dict(zip(json.loads(SCHEMA.read_text())["primary_features.csv"],[case,role,rgi,y,slope,*vals,";".join(miss)])))
    complete=[]
    for f in features:
        for endpoint,ok,reason in [("warming",bool(f["warming_k_decade"]),next((x for x in f["missing_reason"].split(";") if x.startswith("t2m:")),"")),
                                   ("surface_slope",bool(f["slope_deg"]),next((x for x in f["missing_reason"].split(";") if x.startswith("slope:")),""))]:
            complete.append({"candidate_id":f["candidate_id"],"role":f["role"],"rgi_id":f["rgi_id"],"endpoint":endpoint,"complete":ok,"missing_reason":reason})
    ledger={r["candidate_id"]:r["final_cluster"] for r in rows(OUT/"spatial_dependence_ledger.csv")}; contrasts=[]; direct={}
    for case in sorted(ledger):
        group=[f for f in features if f["candidate_id"]==case]; direct[case]=all(not f["missing_reason"] for f in group)
        for endpoint,key in (("warming","warming_k_decade"),("surface_slope","slope_deg")):
            c=next(f for f in group if f["role"]=="case"); ctl=[f for f in group if f["role"]=="control"]
            ok=direct[case] and len(ctl)==20; cv=float(c[key]) if c[key] else None
            if ok:
                vals=[float(f[key]) for f in ctl]; med=median(vals); con=cv-med; allv=vals+[cv]; L=sum(v<cv for v in allv); E=sum(v==cv for v in allv)
                record=[case,ledger[case],endpoint,cv,med,con,100*(L+.5*E)/21,True,""]
            else: record=[case,ledger[case],endpoint,cv if cv is not None else "","","","",False,f"case_set:incomplete_{endpoint}"]
            contrasts.append(dict(zip(json.loads(SCHEMA.read_text())["matched_contrasts.csv"],record)))
    clusters={v:{c for c in ledger if ledger[c]==v} for v in set(ledger.values())}; retained={cl for cl,cs in clusters.items() if all(direct[c] for c in cs)}
    dep=[{"candidate_id":c,"final_cluster":ledger[c],"direct_complete":direct[c],"complete":ledger[c] in retained,
          "missing_reason":"" if ledger[c] in retained else "component:incomplete_case"} for c in sorted(ledger)]
    cc=[]
    for cl in sorted(retained):
        for endpoint in ("warming","surface_slope"):
            rs=[r for r in contrasts if r["final_cluster"]==cl and r["endpoint"]==endpoint]
            casevals=[float(r["case_value"]) for r in rs]; cons=[float(r["contrast"]) for r in rs]
            cc.append({"final_cluster":cl,"endpoint":endpoint,"case_count":len(rs),"contrast":math.fsum(cons)/len(cons),"mean_case_value":math.fsum(casevals)/len(casevals)})
    summaries=[]
    for endpoint in ("warming","surface_slope"):
        vals=[r["contrast"] for r in cc if r["endpoint"]==endpoint]; k,p,med,lo,hi,hl=sign_stats(vals)
        summaries.append({"endpoint":endpoint,"clusters":len(vals),"cases":sum(len(clusters[c]) for c in retained),"positive_clusters":k,"sign_p":p,
          "median_contrast":med,"sign_ci_low":lo,"sign_ci_high":hi,"hodges_lehmann":hl})
    w=next(r["median_contrast"] for r in summaries if r["endpoint"]=="warming"); s=next(r["median_contrast"] for r in summaries if r["endpoint"]=="surface_slope")
    raw=[r["mean_case_value"] for r in cc if r["endpoint"]=="warming"]; a=median(raw) if raw else ""; cases=sum(len(clusters[c]) for c in retained)
    common={r["final_cluster"] for r in cc if r["endpoint"]=="warming"}=={r["final_cluster"] for r in cc if r["endpoint"]=="surface_slope"}
    status,direction=decision(cases>=8 and common,w,s,a)
    dec={"status":status,"direction":direction,"complete_cases":cases,"complete_clusters":len(retained),
      "joint_sign_p":max(r["sign_p"] for r in summaries),"median_component_case_warming_k_decade":a,
      "claim_boundary":"documented cases versus matched RGI comparison objects; descriptive, not risk or causation"}
    schemas=json.loads(SCHEMA.read_text()); outputs={"primary_features.csv":(schemas["primary_features.csv"],features),"case_completeness.csv":(schemas["case_completeness.csv"],complete),
      "matched_contrasts.csv":(schemas["matched_contrasts.csv"],contrasts),"primary_dependence_ledger.csv":(schemas["primary_dependence_ledger.csv"],dep),
      "cluster_contrasts.csv":(schemas["cluster_contrasts.csv"],cc),"primary_summary.csv":(schemas["primary_summary.csv"],summaries)}
    manifest={"status":"primary descriptive matched contrasts","approved_background_sha256":approved_background_sha,"git_commit":git("rev-parse","HEAD"),"decision":dec}
    publish("primary_analysis",outputs,manifest)

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
