#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(".codex-output")
OUT_DIR = ROOT / "list-snapshot"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPHQL = "https://api.github.com/graphql"

LISTS_Q = """
query($after: String) {
  viewer {
    lists(first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { id name }
    }
  }
}
"""

ITEMS_Q = """
query($id: ID!, $after: String) {
  node(id: $id) {
    ... on UserList {
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { ... on Repository { nameWithOwner } }
      }
    }
  }
}
"""


def token() -> str:
    t = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if not t:
        raise RuntimeError("缺少 GITHUB_TOKEN/GH_TOKEN")
    return t


def gql(q: str, tk: str, vars_: dict | None = None) -> dict:
    payload = json.dumps({"query": q, "variables": vars_ or {}}).encode("utf-8")
    req = Request(
        GRAPHQL,
        data=payload,
        headers={
            "Authorization": f"Bearer {tk}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-stars-organizer",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GraphQL HTTPError {e.code}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"GraphQL URLError: {e}") from e

    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


def fetch_all_lists(tk: str) -> List[dict]:
    lists: List[dict] = []
    after = None
    while True:
        data = gql(LISTS_Q, tk, {"after": after})
        conn = (data.get("viewer") or {}).get("lists") or {}
        lists.extend(conn.get("nodes") or [])
        page_info = conn.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break
    return lists


def main() -> None:
    tk = token()
    lists = fetch_all_lists(tk)

    all_rows: List[dict] = []
    for i, li in enumerate(lists, start=1):
        lid, lname = li["id"], li["name"]
        after = None
        while True:
            d = gql(ITEMS_Q, tk, {"id": lid, "after": after})
            conn = d["node"]["items"] if d.get("node") else None
            if not conn:
                break
            nodes = conn.get("nodes") or []
            for n in nodes:
                repo = n.get("nameWithOwner")
                if repo:
                    all_rows.append({"full_name": repo, "list_name": lname})
            if not conn["pageInfo"]["hasNextPage"]:
                break
            after = conn["pageInfo"]["endCursor"]
        if i % 10 == 0 or i == len(lists):
            print(f"[lists] {i}/{len(lists)}")

    membership: Dict[str, List[str]] = {}
    for r in all_rows:
        membership.setdefault(r["full_name"], []).append(r["list_name"])

    (OUT_DIR / "lists.json").write_text(json.dumps(lists, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "membership.json").write_text(json.dumps(membership, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUT_DIR / "membership.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["full_name", "existing_lists"])
        w.writeheader()
        for repo, names in sorted(membership.items()):
            w.writerow({"full_name": repo, "existing_lists": "|".join(sorted(set(names)))})

    print(json.dumps({"list_count": len(lists), "repo_with_lists": len(membership)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
