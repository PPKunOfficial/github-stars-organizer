#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CSV_FILE = Path(".codex-output/starred_categorized_agents_final.csv")
RAW_FILE = Path(".codex-output/starred_raw.ndjson")
OUT_DIR = Path(".codex-output/github-apply")
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

ALLOWED_CATEGORIES = (
    "LLM/智能体",
    "前端/Web",
    "后端/API",
    "Rust/系统",
    "移动端",
    "云原生/运维",
    "数据库/存储",
    "逆向/安全",
    "编译器/语言工具链",
    "学习资源",
    "通用工具/其他",
    "代理工具",
)

LISTS_QUERY = """
query($after: String) {
  viewer {
    login
    lists(first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { id name }
    }
  }
}
"""

CREATE_LIST_MUTATION = """
mutation($name: String!, $description: String, $isPrivate: Boolean) {
  createUserList(input: {name: $name, description: $description, isPrivate: $isPrivate}) {
    list { id name }
  }
}
"""

LIST_ITEMS_QUERY = """
query($id: ID!, $after: String) {
  node(id: $id) {
    ... on UserList {
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          ... on Repository { id nameWithOwner }
        }
      }
    }
  }
}
"""

UPDATE_ITEM_LISTS_MUTATION = """
mutation($itemId: ID!, $listIds: [ID!]!) {
  updateUserListsForItem(input: {itemId: $itemId, listIds: $listIds}) {
    item { ... on Repository { id nameWithOwner } }
    lists { id name }
  }
}
"""


def get_token() -> str:
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("缺少 GITHUB_TOKEN 或 GH_TOKEN")
    return token


def gql(token: str, query: str, variables: Dict[str, Any] | None = None, retries: int = 3) -> Dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = Request(
        GRAPHQL_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "star-classification-applier",
        },
        method="POST",
    )
    for attempt in range(1, retries + 1):
        try:
            with urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if attempt < retries and exc.code in (403, 429, 500, 502, 503):
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"GraphQL HTTPError {exc.code}: {body}") from exc
        except URLError as exc:
            if attempt < retries:
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"GraphQL URLError: {exc}") from exc

        if data.get("errors"):
            msg = json.dumps(data["errors"], ensure_ascii=False)
            if attempt < retries and any("rate limit" in str(e).lower() for e in data["errors"]):
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"GraphQL errors: {msg}")
        return data["data"]
    raise RuntimeError("GraphQL failed after retries")


def load_csv_mapping() -> Tuple[Dict[str, str], List[str]]:
    repo_to_cat: Dict[str, str] = {}
    categories_order: List[str] = []
    seen_cat = set()
    allowed = set(ALLOWED_CATEGORIES)
    invalid: List[str] = []
    with CSV_FILE.open("r", encoding="utf-8", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            repo = (row.get("full_name") or "").strip()
            cat = (row.get("category") or "").strip()
            if not repo and not cat:
                continue
            if not repo:
                invalid.append(f"line {line_no}: <empty repo>\t{cat or '<empty category>'}")
                continue
            if not cat:
                invalid.append(f"line {line_no}: {repo}\t<empty category>")
                continue
            if cat not in allowed:
                invalid.append(f"line {line_no}: {repo}\t{cat}")
                continue
            repo_to_cat[repo] = cat
            if cat not in seen_cat:
                seen_cat.add(cat)
                categories_order.append(cat)
    if invalid:
        details = "\n".join(invalid[:20])
        if len(invalid) > 20:
            details += f"\n... and {len(invalid) - 20} more"
        allowed_text = ", ".join(ALLOWED_CATEGORIES)
        raise RuntimeError(
            "CSV 存在非法分类（或空分类/空仓库），已阻止写入 GitHub。\n"
            f"允许分类仅有: {allowed_text}\n"
            f"问题样例:\n{details}"
        )
    return repo_to_cat, categories_order


def load_repo_node_map() -> Dict[str, str]:
    raw = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    return {row["full_name"]: row["node_id"] for row in raw if row.get("full_name") and row.get("node_id")}


def fetch_lists(token: str) -> Tuple[str, Dict[str, str]]:
    login = ""
    name_to_id: Dict[str, str] = {}
    after = None
    while True:
        data = gql(token, LISTS_QUERY, {"after": after})
        viewer = data.get("viewer") or {}
        if not login:
            login = viewer.get("login") or ""
        conn = viewer.get("lists") or {}
        for n in conn.get("nodes") or []:
            name = n.get("name")
            lid = n.get("id")
            if name and lid:
                name_to_id[name] = lid
        page_info = conn.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break
    if not login:
        raise RuntimeError("无法获取 viewer.login")
    return login, name_to_id


def ensure_lists(token: str, login: str, categories: List[str], name_to_id: Dict[str, str]) -> Dict[str, str]:
    created: Dict[str, str] = {}
    for cat in categories:
        if cat in name_to_id:
            continue
        vars_ = {
            "name": cat,
            "description": f"{login} 的 Star 分类：{cat}",
            "isPrivate": True,
        }
        try:
            data = gql(token, CREATE_LIST_MUTATION, vars_)
            lid = data["createUserList"]["list"]["id"]
            name_to_id[cat] = lid
            created[cat] = lid
        except RuntimeError as exc:
            if "Name has already been taken" in str(exc):
                _, latest = fetch_lists(token)
                if cat in latest:
                    name_to_id[cat] = latest[cat]
                    continue
            raise
    return created


def fetch_item_list_map(token: str, all_list_ids: List[str]) -> Dict[str, List[str]]:
    item_to_lists: Dict[str, List[str]] = {}
    for i, lid in enumerate(all_list_ids, start=1):
        after = None
        while True:
            vars_ = {"id": lid, "after": after}
            data = gql(token, LIST_ITEMS_QUERY, vars_)
            node = data.get("node")
            if not node:
                break
            conn = node["items"]
            nodes = conn.get("nodes") or []
            for n in nodes:
                item_id = n.get("id")
                if not item_id:
                    continue
                item_to_lists.setdefault(item_id, []).append(lid)
            if not conn["pageInfo"]["hasNextPage"]:
                break
            after = conn["pageInfo"]["endCursor"]
        if i % 10 == 0 or i == len(all_list_ids):
            print(f"[scan] lists {i}/{len(all_list_ids)}")
    return item_to_lists


def dedupe(seq: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def main() -> None:
    repo_to_cat, categories = load_csv_mapping()
    repo_to_node = load_repo_node_map()
    token = get_token()

    login, list_name_to_id = fetch_lists(token)
    created = ensure_lists(token, login, categories, list_name_to_id)

    # 拉一次最新 lists，避免并发状态漂移
    _, list_name_to_id = fetch_lists(token)
    all_list_ids = list(list_name_to_id.values())
    item_to_lists = fetch_item_list_map(token, all_list_ids)

    total = 0
    updated = 0
    skipped = 0
    failed = 0
    missing_node = 0
    errors: List[str] = []

    for repo, cat in repo_to_cat.items():
        total += 1
        node_id = repo_to_node.get(repo)
        if not node_id:
            missing_node += 1
            continue
        target_list_id = list_name_to_id.get(cat)
        if not target_list_id:
            failed += 1
            errors.append(f"{repo}\t{cat}\tmissing_target_list")
            continue

        existing = dedupe(item_to_lists.get(node_id, []))
        if target_list_id in existing:
            skipped += 1
            continue

        final_list_ids = dedupe(existing + [target_list_id])
        try:
            gql(token, UPDATE_ITEM_LISTS_MUTATION, {"itemId": node_id, "listIds": final_list_ids})
            updated += 1
            item_to_lists[node_id] = final_list_ids
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"{repo}\t{cat}\t{exc}")

        if total % 50 == 0:
            print(f"[apply] {total}/{len(repo_to_cat)} updated={updated} skipped={skipped} failed={failed}")

    summary = {
        "login": login,
        "source_csv": str(CSV_FILE),
        "categories": len(categories),
        "created_lists": created,
        "total_items": len(repo_to_cat),
        "processed": total,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "missing_node": missing_node,
    }

    (OUT_DIR / "apply_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "apply_errors.log").write_text("\n".join(errors) + ("\n" if errors else ""), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        print(f"[warn] errors={len(errors)}, see {OUT_DIR / 'apply_errors.log'}")


if __name__ == "__main__":
    main()
