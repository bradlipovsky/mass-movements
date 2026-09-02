#!/usr/bin/env python3
"""Freeze the eligible frame and select one blind cell per RGI region."""
import argparse, hashlib, hmac, json, struct, subprocess, tempfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/native_glo90_blind_transfer"
CANDIDATES = OUT / "candidate_windows.csv"
PRESELECTION = OUT / "preselection_manifest.json"
TARGET_TIME = "2026-09-02T06:00:00.000Z"
TARGET_QUERY = "https://beacon.nist.gov/beacon/2.0/pulse/time/next/1788328799999"
UPSTREAM = {
    "data/geographic_sample/frame.csv": "482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879",
    "data/geographic_sample/sample.csv": "1e9164813893e285aeeeaa1a7833e16c87172cbe4d3357e245854ab13966613b",
    "data/global_dem_support/cell_support.csv": "c212449965a543cac03d2b724a8346279b34e2ac87c8d3b0db5e22841c47dd0e",
    "data/denominator/windows.csv": "609185f85bf72e06e487b2345900584f942440f861dbd0a71eff059436fd4412",
    "data/native_glo90_transfer/windows.csv": "9b1fcf63096282afdefd08efe47ef859d304c642a830f514ad94e4c51c63f8c1",
}
REGION_COUNTS = [103, 128, 139, 58, 220, 7, 22, 33, 33, 127, 18, 13, 225, 37, 47, 48, 75, 2]
BOUND = ["protocol/native-glo90-blind-transfer.md", "scripts/native_glo90_blind_selection.py",
         "tests/test_native_glo90_blind_selection.py", "data/native_glo90_blind_transfer/candidate_windows.csv"]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_upstream():
    for name, expected in UPSTREAM.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"upstream file differs: {name}")

def candidates():
    verify_upstream()
    frame = pd.read_csv(ROOT / "data/geographic_sample/frame.csv", dtype={"dominant_region": str})
    sample = set(pd.read_csv(ROOT / "data/geographic_sample/sample.csv").cell_key)
    support = pd.read_csv(ROOT / "data/global_dem_support/cell_support.csv")
    matrix = support.pivot(index="cell_key", columns="instance", values="full_halo_object_support")
    complete = set(matrix.index[matrix.glo30 & matrix.glo90])
    exposed = set()
    for name in ["data/denominator/windows.csv", "data/native_glo90_transfer/windows.csv"]:
        table = pd.read_csv(ROOT / name)
        exposed.update(zip(table.south.astype(int), table.west.astype(int)))
    supported = frame[frame.cell_key.isin(complete)]
    prior_sample = supported.cell_key.isin(sample)
    prior_exposed = pd.Series(list(zip(supported.south, supported.west)), index=supported.index).isin(exposed)
    eligible = supported[~prior_sample & ~prior_exposed].copy()
    counts = eligible.groupby("dominant_region").size().sort_index()
    if (len(supported), int(prior_sample.sum()), int(prior_exposed.sum()), len(eligible)) != (1411, 68, 8, 1335):
        raise ValueError("eligible-population arithmetic differs")
    if counts.index.tolist() != [f"{number:02d}" for number in range(1, 19)] or counts.tolist() != REGION_COUNTS:
        raise ValueError("eligible regional counts differ")
    eligible["eligible_region_cells"] = eligible.dominant_region.map(counts)
    return eligible[["cell_key", "south", "west", "dominant_region", "eligible_region_cells"]].sort_values(
        ["dominant_region", "cell_key"], kind="stable").reset_index(drop=True)

def write_candidates():
    OUT.mkdir(parents=True, exist_ok=True)
    candidates().to_csv(CANDIDATES, index=False, lineterminator="\n")

def file_record(path):
    path = ROOT / path
    return {"bytes": path.stat().st_size, "sha256": digest(path)}

def write_preselection():
    write_candidates()
    payload = {"status": "blind_population_frozen_before_future_pulse", "issue": 31,
               "target_time_utc": TARGET_TIME, "target_query": TARGET_QUERY,
               "population_arithmetic": "1411-68-8=1335", "regions": 18,
               "upstream": UPSTREAM, "files": {name: file_record(name) for name in BOUND}}
    PRESELECTION.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

def verify_preselection():
    frozen = json.loads(PRESELECTION.read_text())
    if frozen.get("status") != "blind_population_frozen_before_future_pulse" or frozen.get("target_query") != TARGET_QUERY:
        raise ValueError("preselection contract differs")
    verify_upstream()
    for name, record in frozen["files"].items():
        if file_record(name) != record:
            raise ValueError(f"preselection file differs: {name}")

def field_string(value):
    value = value.encode()
    return struct.pack(">I", len(value)) + value

def field_hash(value):
    value = bytes.fromhex(value)
    if len(value) != 64:
        raise ValueError("beacon hash field is not 64 bytes")
    return struct.pack(">I", 64) + value

def pulse_message(pulse):
    links = {item["type"]: item["value"] for item in pulse["listValues"]}
    if set(links) != {"previous", "hour", "day", "month", "year"}:
        raise ValueError("beacon skip-list fields differ")
    ext = pulse["external"]
    return b"".join([field_string(pulse["uri"]), field_string(pulse["version"]),
        struct.pack(">I", pulse["cipherSuite"]), struct.pack(">I", pulse["period"]),
        field_hash(pulse["certificateId"]), struct.pack(">Q", pulse["chainIndex"]),
        struct.pack(">Q", pulse["pulseIndex"]), field_string(pulse["timeStamp"]),
        field_hash(pulse["localRandomValue"]), field_hash(ext["sourceId"]),
        struct.pack(">I", ext["statusCode"]), field_hash(ext["value"]),
        *[field_hash(links[name]) for name in ["previous", "hour", "day", "month", "year"]],
        field_hash(pulse["precommitmentValue"]), struct.pack(">I", pulse["statusCode"])])

def verify_pulse(pulse_path, certificate_path):
    verify_preselection()
    pulse = json.loads(Path(pulse_path).read_text())["pulse"]
    certificate = Path(certificate_path).read_bytes()
    fixed = (pulse["version"], pulse["cipherSuite"], pulse["period"], pulse["chainIndex"],
             pulse["timeStamp"], pulse["statusCode"], pulse["external"]["statusCode"])
    if fixed != ("2.0", 0, 60000, 2, TARGET_TIME, 0, 0):
        raise ValueError("beacon identity, time, or status differs")
    if hashlib.sha512(certificate).hexdigest() != pulse["certificateId"]:
        raise ValueError("beacon certificate identifier differs")
    message, signature = pulse_message(pulse), bytes.fromhex(pulse["signatureValue"])
    if hashlib.sha512(message + signature).hexdigest().upper() != pulse["outputValue"]:
        raise ValueError("beacon output hash differs")
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory); cert = directory / "cert.pem"; public = directory / "public.pem"
        signed = directory / "message.bin"; sig = directory / "signature.bin"
        cert.write_bytes(certificate); signed.write_bytes(message); sig.write_bytes(signature)
        key = subprocess.run(["openssl", "x509", "-in", cert, "-pubkey", "-noout"], check=True, capture_output=True).stdout
        public.write_bytes(key)
        subprocess.run(["openssl", "dgst", "-sha512", "-verify", public, "-signature", sig, signed],
                       check=True, capture_output=True)
    return pulse

def select(pulse_path, certificate_path):
    pulse = verify_pulse(pulse_path, certificate_path)
    table = pd.read_csv(CANDIDATES, dtype={"dominant_region": str})
    candidate_sha = digest(CANDIDATES); key = bytes.fromhex(pulse["outputValue"])
    table["random_digest"] = table.cell_key.map(
        lambda value: hmac.new(key, f"{candidate_sha}|{value}".encode(), hashlib.sha256).hexdigest())
    table = table.sort_values(["dominant_region", "random_digest", "cell_key"], kind="stable")
    table["region_rank"] = table.groupby("dominant_region").cumcount() + 1
    table["selected"] = table.region_rank.eq(1).map({True: "yes", False: "no"})
    table["inclusion_probability"] = 1 / table.eligible_region_cells
    table.to_csv(OUT / "randomized_windows.csv", index=False, lineterminator="\n", float_format="%.12f")
    table[table.selected == "yes"].to_csv(OUT / "windows.csv", index=False, lineterminator="\n", float_format="%.12f")
    files = ["data/native_glo90_blind_transfer/randomized_windows.csv", "data/native_glo90_blind_transfer/windows.csv"]
    manifest = {"status": "authenticated_blind_selection_complete", "issue": 31,
                "preselection_manifest_sha256": digest(PRESELECTION), "candidate_windows_sha256": candidate_sha,
                "pulse_json_sha256": digest(pulse_path), "certificate_sha256": digest(certificate_path),
                "pulse_uri": pulse["uri"], "pulse_output_value": pulse["outputValue"],
                "files": {name: file_record(name) for name in files}}
    (OUT / "selection_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["freeze", "select"])
    parser.add_argument("--pulse", type=Path); parser.add_argument("--certificate", type=Path); args = parser.parse_args()
    write_preselection() if args.action == "freeze" else select(args.pulse, args.certificate)
