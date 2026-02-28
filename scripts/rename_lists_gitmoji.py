#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

LISTS_QUERY = """
query($after: String) {
  viewer {
    lists(first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { id name }
    }
  }
}
"""

UPDATE_LIST_MUTATION = """
mutation($listId: ID!, $name: String!) {
  updateUserList(input: {listId: $listId, name: $name}) {
    list { id name }
  }
}
"""

RENAME_MAP = {
    "LLM/智能体": "🤖 llm-agent",
    "逆向/安全": "🔐 reverse-sec",
    "代理工具": "🧭 proxy-tools",
    "云海穿梭": "🧭 proxy-tools",
    "前端/Web": "💄 web-ui",
    "通用工具/其他": "🧰 misc-tools",
    "编译器/语言工具链": "🧪 compiler-toolchain",
    "Rust/系统": "🦀 rust-system",
    "后端/API": "🛠️ backend-api",
    "学习资源": "📚 learning-resources",
    "云原生/运维": "☁️ cloud-devops",
    "数据库/存储": "🗃️ db-storage",
    "移动端": "📱 mobile",
}


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = Request(
        GRAPHQL_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "rename-lists-gitmoji",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTPError {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"URLError: {exc}") from exc

    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


def fetch_all_lists(token: str) -> list[dict]:
    lists: list[dict] = []
    after = None
    while True:
        data = gql(token, LISTS_QUERY, {"after": after})
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
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("缺少 GITHUB_TOKEN/GH_TOKEN")

    lists = fetch_all_lists(token)
    name_to_id = {r["name"]: r["id"] for r in lists}

    renamed = []
    skipped = []
    missing = []

    for old_name, new_name in RENAME_MAP.items():
        list_id = name_to_id.get(old_name)
        if not list_id:
            missing.append(old_name)
            continue
        if old_name == new_name:
            skipped.append(old_name)
            continue
        gql(token, UPDATE_LIST_MUTATION, {"listId": list_id, "name": new_name})
        renamed.append((old_name, new_name))

    summary = {
        "renamed_count": len(renamed),
        "skipped_count": len(skipped),
        "missing_count": len(missing),
        "renamed": renamed,
        "missing": missing,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
