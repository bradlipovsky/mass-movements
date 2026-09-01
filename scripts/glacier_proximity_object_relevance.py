#!/usr/bin/env python3
"""Screen absent DEM delivery units against a conservative RGI dependency zone."""
import argparse, hashlib, json, zipfile
from pathlib import Path
import fiona, pandas as pd, pyproj, shapely
from pyproj import Transformer
from shapely import STRtree, box, force_2d, from_geojson, get_coordinates, make_valid, segmentize, union_all
from shapely.affinity import translate
from shapely.geometry import shape
from shapely.ops import transform
from scripts.denominator_pilot import local_crs, window_geometry
from scripts.geographic_sample import polygon_area_m2, repair_geometry, unwrap

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/glacier_proximity_object_relevance"
RGI_RAW = ROOT / "data/geographic_sample/source_raw/rgi"
FRAME = ROOT / "data/geographic_sample/frame.csv"
RGI_MANIFEST = ROOT / "data/geographic_sample/source_manifest.json"
EXPECTED = ROOT / "data/global_dem_support/expected_objects.csv"
INVENTORY = ROOT / "data/global_dem_support/object_inventory.csv"
ISSUE23 = ROOT / "data/global_dem_support/final_manifest.json"
PRE = OUTPUT / "pregeometry_manifest.json"
ISSUE23_SHA = "a660e3eda35d4fa671e35c03e6c42f3dabad4c3393ca86cd07655d6a0b9d58d3"
PROXIMITY_GUARD_M, DEPENDENCY_GUARD_M, REPAIR_TOL = 101, 1001, 1e-8

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verify_manifest(path, status):
    data = json.loads(Path(path).read_text())
    if data["status"] != status: raise ValueError("manifest status differs")
    for name, item in data["files"].items():
        p = ROOT / name
        if (p.stat().st_size, digest(p)) != (item["bytes"], item["sha256"]): raise ValueError(f"frozen file differs: {name}")
    return data
def report_geometries(south, west):
    crs = local_crs(south, west); geographic, projected = window_geometry(south, west, crs)
    inverse = Transformer.from_crs(crs, 4326, always_xy=True).transform
    envelope = unwrap(transform(inverse, projected.buffer(1100)), west + .5)
    return crs, geographic, projected, envelope
def load_matches(frame):
    envelopes, owners = [], []
    for i, row in frame.iterrows():
        envelope = report_geometries(row.south, row.west)[3]
        for shift in (-360, 0, 360): envelopes.append(translate(envelope, xoff=shift)); owners.append(i)
    tree, matches, seen = STRtree(envelopes), [[] for _ in range(len(frame))], set()
    source = json.loads(RGI_MANIFEST.read_text())
    for item in source["archives"]:
        archive = RGI_RAW / item["filename"]
        if (archive.stat().st_size, digest(archive)) != (item["bytes"], item["sha256"]): raise ValueError("RGI archive differs")
        member = next(x["name"] for x in item["members"] if x["name"].endswith(".shp"))
        with fiona.open(f"zip://{archive}!{member}") as collection:
            for feature in collection:
                rgi_id = feature["properties"]["rgi_id"]
                if rgi_id in seen: raise ValueError(f"duplicate RGI ID: {rgi_id}")
                seen.add(rgi_id); geometry = force_2d(from_geojson(json.dumps(dict(feature["geometry"]))))
                geometry, _ = repair_geometry(geometry, rgi_id, item["region"])
                center = float(get_coordinates(geometry)[0, 0]); query = unwrap(geometry, center)
                for owner in {owners[int(k)] for k in tree.query(query, predicate="intersects")}:
                    matches[owner].append(geometry)
    if len(seen) != 274531 or any(not x for x in matches): raise ValueError("RGI population or cell match differs")
    return matches
def projected_union(geometries, crs, west, cell_key):
    forward = Transformer.from_crs(4326, crs, always_xy=True).transform
    projected, repairs = [], []
    for geometry in geometries:
        item = transform(forward, unwrap(geometry, west + .5))
        if not item.is_valid:
            before = item.area; fixed = make_valid(item, method="linework")
            relative = abs(fixed.area - before) / before
            if fixed.geom_type not in ("Polygon", "MultiPolygon") or not fixed.is_valid or relative > REPAIR_TOL: raise ValueError("projection repair failed")
            repairs.append({"cell_key":cell_key,"input_type":item.geom_type,"output_type":fixed.geom_type,"relative_area_change":relative})
            item = fixed
        projected.append(item)
    glacier = union_all(projected)
    if not glacier.is_valid: raise ValueError("invalid projected union")
    return glacier, repairs
def dependency_region(report, glacier):
    proximity = report.intersection(glacier.buffer(PROXIMITY_GUARD_M)).difference(glacier)
    return proximity, proximity.buffer(DEPENDENCY_GUARD_M) if not proximity.is_empty else proximity
def tile_footprint(latitude, longitude, crs, center):
    geographic = segmentize(box(longitude, latitude, longitude + 1, latitude + 1), .01)
    return transform(Transformer.from_crs(4326, crs, always_xy=True).transform, unwrap(geographic, center))
def geometry(pre_manifest):
    verify_manifest(pre_manifest, "pre_geometry")
    frame = pd.read_csv(FRAME, dtype={"dominant_region":str}).reset_index(drop=True)
    expected = pd.read_csv(EXPECTED, dtype={"dominant_region":str})
    spatial = expected.drop_duplicates(["cell_key","role","latitude","longitude"])
    if (len(frame), len(spatial)) != (1826, 16434): raise ValueError("frozen dimensions differ")
    matches = load_matches(frame); rows, repairs = [], []
    for i, cell in frame.iterrows():
        crs, _, report, _ = report_geometries(cell.south, cell.west)
        glacier, fixed = projected_union(matches[i], crs, cell.west, cell.cell_key); repairs.extend(fixed)
        proximity, dependency = dependency_region(report, glacier)
        candidates = spatial[spatial.cell_key.eq(cell.cell_key)]
        for item in candidates.itertuples(index=False):
            footprint = tile_footprint(item.latitude, item.longitude, crs, cell.west + .5)
            rows.append({"cell_key":cell.cell_key,"south":cell.south,"west":cell.west,"dominant_region":cell.dominant_region,
                "role":item.role,"latitude":item.latitude,"longitude":item.longitude,"proximity_applicable":not proximity.is_empty,
                "screen_relevant":bool(not proximity.is_empty and footprint.intersects(dependency))})
    screen = pd.DataFrame(rows)
    if len(screen) != 16434 or screen.duplicated(["cell_key","latitude","longitude"]).any(): raise ValueError("screen identity differs")
    OUTPUT.mkdir(parents=True, exist_ok=True); screen.to_csv(OUTPUT/"object_screen.csv",index=False,lineterminator="\n")
    pd.DataFrame(repairs,columns=["cell_key","input_type","output_type","relative_area_change"]).to_csv(OUTPUT/"projection_repairs.csv",index=False,lineterminator="\n")
    files={str(p.relative_to(ROOT)):{"bytes":p.stat().st_size,"sha256":digest(p)} for p in [OUTPUT/"object_screen.csv",OUTPUT/"projection_repairs.csv"]}
    (OUTPUT/"geometry_manifest.json").write_text(json.dumps({"status":"geometry_sealed_before_inventory","rows":len(screen),"files":files},indent=2)+"\n")
def join(pre_manifest, geometry_manifest):
    verify_manifest(pre_manifest,"pre_geometry"); verify_manifest(geometry_manifest,"geometry_sealed_before_inventory")
    if digest(ISSUE23) != ISSUE23_SHA: raise ValueError("Issue 23 manifest differs")
    issue23=json.loads(ISSUE23.read_text()); bound=issue23["files"][str(INVENTORY.relative_to(ROOT))]
    if (INVENTORY.stat().st_size,digest(INVENTORY)) != (bound["bytes"],bound["sha256"]): raise ValueError("inventory differs")
    expected=pd.read_csv(EXPECTED,dtype={"dominant_region":str}); screen=pd.read_csv(OUTPUT/"object_screen.csv",dtype={"dominant_region":str}); inventory=pd.read_csv(INVENTORY)
    keys=["cell_key","south","west","dominant_region","role","latitude","longitude"]
    out=expected.merge(screen,on=keys,validate="many_to_one"); present=set(zip(inventory.instance,inventory.object_id))
    out["listed"]=[(x.instance,x.object_id) in present for x in out.itertuples()]
    out["state"]="listed"; out.loc[~out.listed & ~out.screen_relevant,"state"]="absent_proved_irrelevant"; out.loc[~out.listed & out.screen_relevant,"state"]="absent_relevance_unresolved"
    out.to_csv(OUTPUT/"object_support.csv",index=False,lineterminator="\n")
    group_keys=["cell_key","south","west","dominant_region","instance"]
    cells=out.groupby(group_keys,sort=False).agg(proximity_applicable=("proximity_applicable","first"),screen_relevant_objects=("screen_relevant","sum"),listed_relevant_objects=("listed",lambda x: int((x & out.loc[x.index,"screen_relevant"]).sum())),absent_proved_irrelevant=("state",lambda x:int((x=="absent_proved_irrelevant").sum())),absent_relevance_unresolved=("state",lambda x:int((x=="absent_relevance_unresolved").sum()))).reset_index()
    cells["cell_state"]="all_relevant_objects_listed"; cells.loc[~cells.proximity_applicable,"cell_state"]="not_applicable"; cells.loc[cells.absent_relevance_unresolved.gt(0),"cell_state"]="unresolved"
    cells["latitude_band_south"]=(cells.south//10)*10; cells.to_csv(OUTPUT/"cell_support.csv",index=False,lineterminator="\n")
    groups=[]
    for dimension,column in [("region","dominant_region"),("latitude","latitude_band_south")]:
        for (instance,label),g in cells.groupby(["instance",column],sort=True):
            groups.append({"dimension":dimension,"group":label,"instance":instance,"population_cells":len(g),"all_relevant_objects_listed_cells":int((g.cell_state=="all_relevant_objects_listed").sum()),"unresolved_cells":int((g.cell_state=="unresolved").sum()),"not_applicable_cells":int((g.cell_state=="not_applicable").sum())})
    pd.DataFrame(groups).to_csv(OUTPUT/"group_support.csv",index=False,lineterminator="\n")
    summary={i:{s:int((g.cell_state==s).sum()) for s in ["all_relevant_objects_listed","unresolved","not_applicable"]} for i,g in cells.groupby("instance")}
    (OUTPUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("action",choices=["geometry","join"]); parser.add_argument("--pre-manifest",type=Path,required=True); parser.add_argument("--geometry-manifest",type=Path)
    args=parser.parse_args(); geometry(args.pre_manifest) if args.action=="geometry" else join(args.pre_manifest,args.geometry_manifest)
