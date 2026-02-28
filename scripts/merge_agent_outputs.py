#!/usr/bin/env python3
from __future__ import annotations

import csv
import glob
import json
from collections import Counter
from pathlib import Path

ROOT = Path(".codex-output")
IN_DIR = ROOT / "agent-classify"
MASTER = IN_DIR / "input_master.csv"
OUT = ROOT / "starred_categorized_agents_final.csv"


def main() -> None:
    master = {}
    with MASTER.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            master[r["idx"]] = r

    out_rows = {}
    dup = []
    for p in glob.glob(str(IN_DIR / "out_chunk_*.csv")):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                idx = r["idx"]
                if idx in out_rows:
                    dup.append(idx)
                out_rows[idx] = r

    missing = [k for k in master if k not in out_rows]
    extra = [k for k in out_rows if k not in master]
    if missing or dup or extra:
        raise RuntimeError(json.dumps({"missing": len(missing), "dup": len(dup), "extra": len(extra)}, ensure_ascii=False))

    final = []
    for idx in sorted(master, key=lambda x: int(x)):
        m, o = master[idx], out_rows[idx]
        cat = (o.get("category") or "").strip()
        reason = (o.get("reason") or "").strip()
        if not cat:
            raise RuntimeError(f"idx={idx} empty category")
        final.append(
            {
                "idx": idx,
                "full_name": m["full_name"],
                "category": cat,
                "reason": reason,
                "language": m["language"],
                "description": m["description"],
                "topics": m["topics"],
                "existing_lists": m.get("existing_lists", ""),
                "stars": m["stars"],
                "html_url": m["html_url"],
            }
        )

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(final[0].keys()))
        w.writeheader()
        w.writerows(final)

    c = Counter(r["category"] for r in final)
    print(json.dumps({"rows": len(final), "categories": c}, ensure_ascii=False, default=dict, indent=2))


if __name__ == "__main__":
    main()
