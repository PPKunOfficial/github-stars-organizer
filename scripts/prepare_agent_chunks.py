#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(".codex-output")
RAW_FILE = ROOT / "starred_raw.ndjson"
README_CACHE = ROOT / "readme_cache.json"
MEMBERSHIP_CSV = ROOT / "list-snapshot" / "membership.csv"
OUT_DIR = ROOT / "agent-classify"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIELDNAMES = [
    "idx",
    "full_name",
    "language",
    "description",
    "topics",
    "readme_excerpt",
    "existing_lists",
    "stars",
    "html_url",
]


def split_rows(rows: list[dict], chunk_num: int) -> list[list[dict]]:
    base, extra = divmod(len(rows), chunk_num)
    chunks: list[list[dict]] = []
    start = 0
    for i in range(chunk_num):
        end = start + base + (1 if i < extra else 0)
        chunks.append(rows[start:end])
        start = end
    return chunks


def main() -> None:
    raw = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    cache = json.loads(README_CACHE.read_text(encoding="utf-8")) if README_CACHE.exists() else {}

    existing = {}
    if MEMBERSHIP_CSV.exists():
        with MEMBERSHIP_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing[r["full_name"]] = r.get("existing_lists", "")

    rows = []
    for i, r in enumerate(raw, start=1):
        readme = (cache.get(r.get("full_name", ""), "") or "")
        if len(readme) > 2800:
            readme = readme[:2800]
        rows.append(
            {
                "idx": i,
                "full_name": r.get("full_name", ""),
                "language": r.get("language") or "Unknown",
                "description": (r.get("description") or "").replace("\n", " ").strip(),
                "topics": "|".join(r.get("topics") or []),
                "readme_excerpt": readme,
                "existing_lists": existing.get(r.get("full_name", ""), ""),
                "stars": r.get("stargazers_count") or 0,
                "html_url": r.get("html_url", ""),
            }
        )

    master = OUT_DIR / "input_master.csv"
    with master.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)

    for p in OUT_DIR.glob("chunk_*.csv"):
        p.unlink()

    total = len(rows)
    if total == 0:
        chunk_num = 0
        size = 0
    else:
        chunk_num = min(6, total)
        size = math.ceil(total / chunk_num)
        for i, part in enumerate(split_rows(rows, chunk_num), start=1):
            p = OUT_DIR / f"chunk_{i}.csv"
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDNAMES)
                w.writeheader()
                w.writerows(part)

    print(json.dumps({"total": total, "chunks": chunk_num, "chunk_size": size}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
