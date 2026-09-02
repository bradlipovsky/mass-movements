#!/usr/bin/env python3
"""Freeze the eligible frame and select one blind cell per RGI region."""
import argparse, datetime, hashlib, hmac, json, struct, subprocess, tempfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/native_glo90_blind_transfer"
CANDIDATES = OUT / "candidate_windows.csv"
PRESELECTION = OUT / "preselection_manifest.json"
BEACON = OUT / "beacon"
PULSE, PREVIOUS, CERTIFICATE = BEACON / "pulse.json", BEACON / "previous_pulse.json", BEACON / "certificate.pem"
ISSUER = ROOT / "data/geographic_sample/beacon/verification/issuer_certificate.pem"
TARGET_TIME = "2026-09-02T06:00:00.000Z"
TARGET_QUERY = "https://beacon.nist.gov/beacon/2.0/pulse/time/next/1788328799999"
NIST_CERTIFICATE_ID = ("528943a555f5f8ca54423be6dfb95925a35c7b552046420e7d7cd072058a14d65"
                       "36ad3a8e9754b6582f164a90b0cd86a65d659f5426a2659a947595d1c816c8c")
UPSTREAM = {
    "data/geographic_sample/frame.csv": "482c9d585777317ab69363481db3df1011e2d4e8ce84c3826b151406cace9879",
    "data/geographic_sample/sample.csv": "1e9164813893e285aeeeaa1a7833e16c87172cbe4d3357e245854ab13966613b",
    "data/global_dem_support/cell_support.csv": "c212449965a543cac03d2b724a8346279b34e2ac87c8d3b0db5e22841c47dd0e",
    "data/denominator/windows.csv": "609185f85bf72e06e487b2345900584f942440f861dbd0a71eff059436fd4412",
    "data/native_glo90_transfer/windows.csv": "9b1fcf63096282afdefd08efe47ef859d304c642a830f514ad94e4c51c63f8c1",
    "data/geographic_sample/beacon/pulse.json": "1e160ddf2bf6604d675563c484ca87f94c85eee308a6bc4ae3188a1a6774103f",
    "data/geographic_sample/beacon/previous_pulse.json": "d7fdec432b4cc4b6bf48bf0c6fd685a8d0e8729093155805fcaba60e455eb226",
    "data/geographic_sample/beacon/certificate.pem": "acd33ba715a14c1d2c1601983c38cb7e671de151c3536fdf25097f28f9533229",
    "data/geographic_sample/beacon/verification/issuer_certificate.pem": "6601f41fceefbe7523a6a2e746938de57fc24e99426b7bea58d1867dbee1be5e",
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

def verify_preselection(approved_sha256):
    if digest(PRESELECTION) != approved_sha256:
        raise ValueError("unapproved preselection manifest")
    frozen = json.loads(PRESELECTION.read_text())
    fixed = (set(frozen), frozen.get("status"), frozen.get("issue"), frozen.get("target_time_utc"),
             frozen.get("target_query"), frozen.get("population_arithmetic"), frozen.get("regions"),
             frozen.get("upstream"), set(frozen.get("files", {})))
    expected = ({"status", "issue", "target_time_utc", "target_query", "population_arithmetic", "regions", "upstream", "files"},
                "blind_population_frozen_before_future_pulse", 31, TARGET_TIME, TARGET_QUERY,
                "1411-68-8=1335", 18, UPSTREAM, set(BOUND))
    if fixed != expected:
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

def verify_identity(pulse, expected_time):
    uri = f"https://beacon.nist.gov/beacon/2.0/chain/2/pulse/{pulse['pulseIndex']}"
    fixed = (pulse["version"], pulse["cipherSuite"], pulse["period"], pulse["chainIndex"],
             pulse["timeStamp"], pulse["statusCode"], pulse["external"]["statusCode"],
             pulse["certificateId"], pulse["uri"])
    if fixed != ("2.0", 0, 60000, 2, expected_time, 0, 0, NIST_CERTIFICATE_ID, uri):
        raise ValueError("beacon identity, time, or status differs")

def verify_certificate(certificate):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "certificate.pem"; path.write_bytes(certificate)
        converted = subprocess.run(["openssl", "x509", "-in", path, "-outform", "DER"], capture_output=True)
        if converted.returncode or hashlib.sha512(converted.stdout).hexdigest() != NIST_CERTIFICATE_ID:
            raise ValueError("beacon certificate identifier differs")
        trusted = subprocess.run(["openssl", "verify", "-attime", "1788328800", "-purpose", "any",
                                  "-CAfile", "/etc/pki/tls/certs/ca-bundle.crt", "-untrusted", ISSUER, path],
                                 capture_output=True)
        if trusted.returncode:
            raise ValueError("beacon certificate trust chain differs")

def verify_signature(pulse, certificate):
    verify_certificate(certificate)
    message, signature = pulse_message(pulse), bytes.fromhex(pulse["signatureValue"])
    if hashlib.sha512(message + signature).hexdigest().upper() != pulse["outputValue"]:
        raise ValueError("beacon output hash differs")
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory); cert = directory / "cert.pem"; public = directory / "public.pem"
        signed = directory / "message.bin"; sig = directory / "signature.bin"
        cert.write_bytes(certificate); signed.write_bytes(message); sig.write_bytes(signature)
        key = subprocess.run(["openssl", "x509", "-in", cert, "-pubkey", "-noout"], check=True, capture_output=True).stdout
        public.write_bytes(key)
        dates = subprocess.run(["openssl", "x509", "-in", cert, "-noout", "-dates"],
                               check=True, capture_output=True, text=True).stdout.splitlines()
        parsed = [datetime.datetime.strptime(item.split("=", 1)[1], "%b %d %H:%M:%S %Y GMT").replace(
            tzinfo=datetime.timezone.utc) for item in dates]
        target = datetime.datetime.fromisoformat(TARGET_TIME.replace("Z", "+00:00"))
        if not parsed[0] <= target <= parsed[1]:
            raise ValueError("beacon certificate invalid at target time")
        checked = subprocess.run(["openssl", "dgst", "-sha512", "-verify", public,
                                  "-signature", sig, signed], capture_output=True)
        if checked.returncode:
            raise ValueError("beacon signature differs")

def verify_links(pulse, previous):
    links = {item["type"]: item for item in pulse["listValues"]}
    linked = (pulse["pulseIndex"] == previous["pulseIndex"] + 1,
              links["previous"]["uri"] == previous["uri"], links["previous"]["value"] == previous["outputValue"],
              hashlib.sha512(bytes.fromhex(pulse["localRandomValue"])).hexdigest().upper() == previous["precommitmentValue"])
    if not all(linked):
        raise ValueError("beacon previous-pulse or precommitment link differs")

def verify_pulse(pulse_path, previous_path, certificate_path, approved_sha256):
    verify_preselection(approved_sha256)
    if tuple(Path(item).resolve() for item in [pulse_path, previous_path, certificate_path]) != tuple(
            item.resolve() for item in [PULSE, PREVIOUS, CERTIFICATE]):
        raise ValueError("beacon inputs are not retained at canonical paths")
    pulse = json.loads(Path(pulse_path).read_text())["pulse"]
    previous = json.loads(Path(previous_path).read_text())["pulse"]
    certificate = Path(certificate_path).read_bytes()
    verify_identity(pulse, TARGET_TIME); verify_identity(previous, "2026-09-02T05:59:00.000Z")
    verify_signature(previous, certificate); verify_signature(pulse, certificate)
    verify_links(pulse, previous)
    return pulse

def rank_candidates(table, key, candidate_sha):
    table = table.copy()
    table["random_digest"] = table.cell_key.map(
        lambda value: hmac.new(key, f"{candidate_sha}|{value}".encode(), hashlib.sha256).hexdigest())
    if not table.random_digest.is_unique:
        raise ValueError("HMAC collision in candidate population")
    table = table.sort_values(["dominant_region", "random_digest", "cell_key"], kind="stable")
    table["region_rank"] = table.groupby("dominant_region").cumcount() + 1
    table["selected"] = table.region_rank.eq(1).map({True: "yes", False: "no"})
    table["inclusion_probability"] = 1 / table.eligible_region_cells
    return table

def overall_status(statuses):
    statuses = list(statuses)
    if len(statuses) != 36 or not set(statuses) <= {"PASS", "FAIL", "INDETERMINATE"}:
        raise ValueError("decision population differs")
    if "FAIL" in statuses: return "FAIL"
    if "INDETERMINATE" in statuses: return "INDETERMINATE"
    return "PASS"

def select(pulse_path, previous_path, certificate_path, approved_sha256):
    pulse = verify_pulse(pulse_path, previous_path, certificate_path, approved_sha256)
    table = pd.read_csv(CANDIDATES, dtype={"dominant_region": str})
    candidate_sha = digest(CANDIDATES); key = bytes.fromhex(pulse["outputValue"])
    table = rank_candidates(table, key, candidate_sha)
    table.to_csv(OUT / "randomized_windows.csv", index=False, lineterminator="\n", float_format="%.12f")
    table[table.selected == "yes"].to_csv(OUT / "windows.csv", index=False, lineterminator="\n", float_format="%.12f")
    files = ["data/native_glo90_blind_transfer/beacon/pulse.json",
             "data/native_glo90_blind_transfer/beacon/previous_pulse.json",
             "data/native_glo90_blind_transfer/beacon/certificate.pem",
             "data/native_glo90_blind_transfer/randomized_windows.csv",
             "data/native_glo90_blind_transfer/windows.csv"]
    manifest = {"status": "authenticated_blind_selection_complete", "issue": 31,
                "preselection_manifest_sha256": digest(PRESELECTION), "candidate_windows_sha256": candidate_sha,
                "pulse_json_sha256": digest(pulse_path), "previous_pulse_json_sha256": digest(previous_path),
                "certificate_sha256": digest(certificate_path),
                "pulse_uri": pulse["uri"], "pulse_output_value": pulse["outputValue"],
                "files": {name: file_record(name) for name in files}}
    (OUT / "selection_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["freeze", "select"])
    parser.add_argument("--pulse", type=Path); parser.add_argument("--previous", type=Path)
    parser.add_argument("--certificate", type=Path); parser.add_argument("--approved-preselection-sha256")
    args = parser.parse_args()
    write_preselection() if args.action == "freeze" else select(
        args.pulse, args.previous, args.certificate, args.approved_preselection_sha256)
