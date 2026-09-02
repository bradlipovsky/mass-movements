import csv, json, math, sys
import numpy as np
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import glacier_primary_analysis as g

def test_registered_pins_and_schema():
    g.checked_inputs(); s=json.loads(g.SCHEMA.read_text())
    assert s["amends"].endswith("outcome artifacts only") and set(s["artifacts"])==set().union(*(x[1] for x in g.STAGES.values()))|{"glacier_year_t2m.csv","background_features.csv","era5_access_ledger.csv","era5_cell_year.csv","rgi_surface_features.csv"}
    assert len(g.participants())==210 and len({r[2] for r in g.participants()})==207
def test_median_midrank_reference():
    assert g.matched_value(10,list(range(20)))==pytest.approx((9.5,.5,1100/21))
def test_trend_exact_hac_reference():
    v=[6,4,8]+list(range(8,25)); tr,change,se,ts=g.trend(v)
    assert tr==pytest.approx(10) and change==pytest.approx(19)
    assert se==pytest.approx(0.1566499580061383) and ts==pytest.approx(10)
    line=[3+2*i for i in range(20)]; assert g.trend(line)[:3]==pytest.approx((20,38,0))
    shifted=[x+100 for x in v]; assert g.trend(shifted)[0:4]==pytest.approx(g.trend(v)[0:4])
def test_sign_reference_ci_and_hl():
    assert g.sign_stats([1]*9+[-1]*2)[1]==67/2048
    assert g.sign_stats([1]*9+[-1])[1]==11/1024
    assert g.sign_stats([0,-1])[1]==1
    assert g.sign_stats(range(1,6))[3:5]==("","")
    assert g.sign_stats(range(1,7))[3:5]==("1","6")
    assert g.sign_stats([1,2,100])[-1]==26.25
def test_decision_truth_table():
    for w in (-1,1):
        for s in (-1,1):
            for a in (-1,1):
                status,direction=g.decision(True,w,s,a); assert status=="DESCRIPTIVE_ONLY"
                expected="consistent" if w>0 and s>0 and a>0 else "inconsistent" if w<=0 and s<=0 else "mixed"
                assert direction==expected
    assert g.decision(False,1,1,1)==("INDETERMINATE",None)
def test_weighted_mean_and_no_renormalization():
    req=[{"rgi_id":"g","index_year":"2001","year":"2000","latitude":x,"longitude":"0"} for x in ("0","1")]
    weights=[{"rgi_id":"g","latitude":x,"longitude":"0","weight":w} for x,w in (("0",".25"),("1",".75"))]
    era=[{"latitude":x,"longitude":"0","year":"2000","t2m_mean_k":v} for x,v in (("0","270"),("1","274"))]
    assert g.glacier_years(req,weights,era)[0]["t2m_mean_k"]=="273"
    era[1]["t2m_mean_k"]=""; assert g.glacier_years(req,weights,era)[0]["t2m_mean_k"]==""
def test_exact_calendar_rejects_duplicate_with_same_count():
    good=np.arange(np.datetime64("2000-01-01T00"),np.datetime64("2002-01-01T00"),np.timedelta64(1,"h"))
    assert g.calendar_slice(good,2000)==(0,8784) and g.calendar_slice(good,2001)==(8784,8760)
    bad=good.copy(); bad[2]=bad[1]
    with pytest.raises(ValueError): g.calendar_slice(bad,2000)
    with pytest.raises(ValueError): g.calendar_slice(np.insert(good,8784,good[8783]),2000)
    with pytest.raises(ValueError): g.calendar_slice(good.astype("datetime64[m]")+np.timedelta64(30,"m"),2000)
def test_coordinate_lookup_is_exact_and_unique():
    assert g.coordinate_index(np.array([.25,.5]),.25)==0
    with pytest.raises(ValueError): g.coordinate_index(np.array([.249,.5]),.25)
    with pytest.raises(ValueError): g.coordinate_index(np.array([.25,.25]),.25)
def test_component_weighting_and_common_exclusion():
    rel=[]; bg=[]; spatial=[]
    for case,cluster,case_w in (("c1","A",12),("c2","A",14),("c3","B",9)):
        spatial.append({"candidate_id":case,"initial_cluster":cluster,"final_cluster":cluster})
        rel.append((case,"case",case,2001)); ids=[case]+[f"{case}x{i}" for i in range(20)]
        for i,rgi in enumerate(ids):
            if i: rel.append((case,"control",rgi,2001))
            bg.append({"rgi_id":rgi,"index_year":"2001","t2m_trend_k_decade":str(case_w if i==0 else 10),"t2m_change_k":"1",
              "t2m_hac_se_k_decade":".1","theil_sen_k_decade":"1","slope_deg":str(case_w if i==0 else 10),"missing_reason":""})
    out=g.build_analysis(rel,bg,spatial); cc=out["cluster_contrasts.csv"]
    assert [r["contrast"] for r in cc if r["endpoint"]=="t2m_trend_k_decade"]==[3,-1]
    broken=next(r for r in bg if r["rgi_id"]=="c2x0"); broken["slope_deg"]=""; broken["missing_reason"]="slope:missing_or_invalid"
    out=g.build_analysis(rel,bg,spatial); assert {r["final_cluster"] for r in out["cluster_contrasts.csv"]}=={"B"}
    assert next(r for r in out["dependence_ledger.csv"] if r["candidate_id"]=="c1")["direct_complete"] is True
    assert "c2:slope_deg:c2x0" in next(r for r in out["dependence_ledger.csv"] if r["candidate_id"]=="c1")["missing_reason"]
def test_publish_refuses_collision_and_rolls_back(tmp_path,monkeypatch):
    monkeypatch.setattr(g,"OUT",tmp_path); monkeypatch.setitem(g.STAGES,"x",("x",{"a.csv"})); monkeypatch.setattr(g,"validate_table",lambda *x:None); fields=["x"]
    g.publish("x",{"a.csv":(fields,[{"x":1}])},{"status":"x"})
    with pytest.raises(FileExistsError): g.publish("x",{"a.csv":(fields,[])},{})
    (tmp_path/"a.csv").unlink(); (tmp_path/"x_manifest.json").unlink()
    with pytest.raises(RuntimeError): g.publish("x",{"a.csv":(fields,[{"x":1}])},{},fail_after=1)
    assert not list(tmp_path.iterdir())
