import csv, json, math, sys
import numpy as np
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import glacier_primary_analysis as g

def test_registered_pins_and_schema():
    g.checked_inputs(); s=json.loads(g.SCHEMA.read_text())
    assert set(s)=={"primary_access_requests.csv","rgi_surface_features.csv","era5_cell_year.csv","era5_access_ledger.csv","primary_features.csv","case_completeness.csv","matched_contrasts.csv","primary_dependence_ledger.csv","cluster_contrasts.csv","primary_summary.csv"}
    assert len(g.participants())==210 and len({r[2] for r in g.participants()})==207
def test_median_midrank_reference():
    ctl=list(range(20)); case=10; assert g.median(ctl)==9.5
    allv=ctl+[case]; assert 100*(sum(v<case for v in allv)+.5*sum(v==case for v in allv))/21==1100/21
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
    assert math.fsum([.25*270,.75*274])==273
    with pytest.raises(KeyError): math.fsum(w*{("a",2000):270}[(c,2000)] for c,w in [("a",.25),("b",.75)])
def test_exact_calendar_rejects_duplicate_with_same_count():
    good=np.arange(np.datetime64("2000-01-01T00"),np.datetime64("2002-01-01T00"),np.timedelta64(1,"h"))
    assert g.calendar_slice(good,2000)==(0,8784) and g.calendar_slice(good,2001)==(8784,8760)
    bad=good.copy(); bad[2]=bad[1]
    with pytest.raises(ValueError): g.calendar_slice(bad,2000)
def test_publish_refuses_collision_and_rolls_back(tmp_path,monkeypatch):
    monkeypatch.setattr(g,"OUT",tmp_path); fields=["x"]
    g.publish("x",{"a.csv":(fields,[{"x":1}])},{"status":"x"})
    with pytest.raises(FileExistsError): g.publish("x",{"a.csv":(fields,[])},{})
    (tmp_path/"a.csv").unlink(); (tmp_path/"x_manifest.json").unlink()
    with pytest.raises(RuntimeError): g.publish("x",{"a.csv":(fields,[{"x":1}])},{},fail_after=1)
    assert not list(tmp_path.iterdir())
