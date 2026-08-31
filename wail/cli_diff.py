import json
import os
import sys
from collections import defaultdict


def load_traces(path):
    traces = []
    for fname in os.listdir(path):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(path, fname), "r", encoding="utf-8") as f:
            traces.append(json.load(f))
    return traces


def diff_group(traces):
    diffs = []

    base = traces[0]
    for other in traces[1:]:
        diff = {}

        for key in ("duration_ms", "retry_count"):
            if base.get(key) != other.get(key):
                diff[key] = {
                    "base": base.get(key),
                    "other": other.get(key),
                }

        base_risks = set(base.get("runtime_risk_signals", []))
        other_risks = set(other.get("runtime_risk_signals", []))
        if base_risks != other_risks:
            diff["runtime_risk_signals"] = {
                "base": list(base_risks),
                "other": list(other_risks),
            }

        if diff:
            diffs.append(
                {
                    "trace_a": base["trace_id"],
                    "trace_b": other["trace_id"],
                    "diff": diff,
                }
            )

    return diffs


def main():
    if len(sys.argv) < 2:
        print("Usage: wail diff <trace_dir>")
        sys.exit(1)

    path = sys.argv[1]
    traces = load_traces(path)

    groups = defaultdict(list)
    for t in traces:
        fp = t.get("request_fingerprint")
        if fp:
            groups[fp].append(t)

    any_diff = False

    for fp, group in groups.items():
        if len(group) < 2:
            continue

        diffs = diff_group(group)
        if diffs:
            any_diff = True
            print(f"\nFINGERPRINT {fp[:12]}…")
            for d in diffs:
                print(f"  {d['trace_a']} ↔ {d['trace_b']}")
                for k, v in d["diff"].items():
                    print(f"    - {k}: {v['base']} → {v['other']}")

    if not any_diff:
        print("No deterministic diffs found.")


if __name__ == "__main__":
    main()
