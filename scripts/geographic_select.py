"""Order the frozen frame from an already verified NIST Beacon pulse."""

import argparse, csv, hashlib, hmac, json
from collections import defaultdict
from pathlib import Path

def order_frame(frame_path, output_value):
    key = bytes.fromhex(output_value)
    if len(output_value) != 128 or len(key) != 64:
        raise ValueError("outputValue must be 128 hexadecimal characters")
    raw = frame_path.read_bytes()
    frame_hash = hashlib.sha256(raw).hexdigest()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    groups = defaultdict(list)
    for row in rows:
        message = f"{frame_hash}|{row['cell_key']}".encode()
        row["random_digest"] = hmac.new(key, message, hashlib.sha256).hexdigest()
        groups[row["dominant_region"]].append(row)
    if len({row["random_digest"] for row in rows}) != len(rows):
        raise ValueError("HMAC digest collision")
    ordered = []
    for region in sorted(groups):
        group = sorted(groups[region], key=lambda row: row["random_digest"])
        population, sample = int(group[0]["stratum_population_cells"]), int(group[0]["stratum_sample_cells"])
        pair = sample * (sample - 1) / (population * (population - 1)) if population > 1 else 1.0
        for rank, row in enumerate(group, 1):
            row.update({"stratum_rank": rank, "selected": "yes" if rank <= sample else "no",
                        "same_stratum_pair_probability": f"{pair:.12f}",
                        "cross_stratum_pair_rule": "product_of_first_order_probabilities"})
            ordered.append(row)
    return ordered
def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", type=Path, default=Path("data/geographic_sample/frame.csv"))
    parser.add_argument("--pulse", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/geographic_sample/randomized_frame.csv"))
    parser.add_argument("--sample", type=Path, default=Path("data/geographic_sample/sample.csv"))
    args = parser.parse_args()
    pulse = json.loads(args.pulse.read_text())["pulse"]
    ordered = order_frame(args.frame, pulse["outputValue"])
    write_rows(args.output, ordered); write_rows(args.sample, [row for row in ordered if row["selected"] == "yes"])
